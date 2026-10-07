"""Escenario 4: seguimiento del progreso y alertas tempranas (AgenteMonitor).

Los indicadores y las alertas se calculan con reglas deterministas (verificables en las
pruebas); el AgenteMonitor redacta el reporte y las acciones de acompañamiento.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from .agents import crear_monitor, ejecutar_agente, prompt
from .memory import MemoriaEstudiantes
from .settings import cargar_lms, cargar_perfiles
from .trace import registrar

UMBRAL_REZAGO = 3.0
UMBRAL_CONCEPTO_REPETIDO = 3
UMBRAL_DIAS_SIN_ACCESO = 10


def calcular_indicadores(memoria: MemoriaEstudiantes) -> list[dict]:
    lms = cargar_lms()
    corte = date.fromisoformat(lms["fecha_corte"])
    indicadores = []
    for estudiante_id, perfil in cargar_perfiles().items():
        datos = lms["estudiantes"][estudiante_id]
        notas = [e["nota"] for e in datos["entregas"] if e["entregado"]]
        conceptos = Counter(c for e in datos["entregas"] for c in e["conceptos_fallados"])
        mem = memoria.cargar(estudiante_id)
        conceptos.update(mem["conceptos_dificultad"])
        indicadores.append(
            {
                "estudiante_id": estudiante_id,
                "nombre": perfil["nombre"],
                "promedio": round(sum(notas) / len(notas), 2) if notas else 0.0,
                "tendencia": round(notas[-1] - notas[0], 2) if len(notas) > 1 else 0.0,
                "entregas_faltantes": sum(1 for e in datos["entregas"] if not e["entregado"]),
                "dias_sin_acceso": (corte - date.fromisoformat(datos["ultimo_acceso"])).days,
                "mensajes_foro": datos["mensajes_foro"],
                "conceptos_repetidos": {c: n for c, n in conceptos.items() if n >= 2},
                "tutorias": len(mem["interacciones"]),
                "intentos_obtener_solucion": mem["intentos_obtener_solucion"],
            }
        )
    return indicadores


def alertas_por_reglas(indicadores: list[dict]) -> list[dict]:
    alertas = []
    for ind in indicadores:
        def alerta(tipo: str, prioridad: str, evidencia: str):
            alertas.append({"estudiante_id": ind["estudiante_id"], "nombre": ind["nombre"],
                            "tipo": tipo, "prioridad": prioridad, "evidencia": evidencia})

        if ind["entregas_faltantes"] >= 2 or ind["dias_sin_acceso"] >= UMBRAL_DIAS_SIN_ACCESO or ind["mensajes_foro"] == 0:
            alerta("participa poco", "alta",
                   f"{ind['entregas_faltantes']} entregas faltantes, {ind['dias_sin_acceso']} días sin acceso, "
                   f"{ind['mensajes_foro']} mensajes en foro")
        repetidos = {c: n for c, n in ind["conceptos_repetidos"].items() if n >= UMBRAL_CONCEPTO_REPETIDO}
        if repetidos:
            alerta("falla repetida", "alta", "conceptos fallados repetidamente: "
                   + ", ".join(f"{c} ({n} veces)" for c, n in repetidos.items()))
        if ind["promedio"] < UMBRAL_REZAGO:
            alerta("rezago", "media", f"promedio {ind['promedio']} (tendencia {ind['tendencia']:+})")
        if ind["intentos_obtener_solucion"] >= 2:
            alerta("busca atajos", "media", f"{ind['intentos_obtener_solucion']} intentos de obtener la solución")
    return alertas


def ejecutar_monitor(memoria: MemoriaEstudiantes | None = None) -> dict:
    memoria = memoria or MemoriaEstudiantes()
    indicadores = calcular_indicadores(memoria)
    alertas = alertas_por_reglas(indicadores)
    registrar("monitor_reglas", alertas=alertas)

    tabla = "\n".join(
        f"- {i['nombre']} ({i['estudiante_id']}): promedio {i['promedio']}, tendencia {i['tendencia']:+}, "
        f"entregas faltantes {i['entregas_faltantes']}, días sin acceso {i['dias_sin_acceso']}, "
        f"foro {i['mensajes_foro']}, conceptos repetidos {i['conceptos_repetidos'] or 'ninguno'}, "
        f"tutorías {i['tutorias']}, intentos de pedir solución {i['intentos_obtener_solucion']}"
        for i in indicadores
    )
    reglas = "\n".join(f"- {a['nombre']}: {a['tipo']} (prioridad {a['prioridad']}) — {a['evidencia']}" for a in alertas)
    entrada = prompt("monitoreo", fecha_corte=cargar_lms()["fecha_corte"], indicadores=tabla,
                     alertas_reglas=reglas or "(ninguna)")
    reporte = ejecutar_agente(crear_monitor(), entrada).raw.strip()
    registrar("monitor_reporte", reporte=reporte)
    return {"indicadores": indicadores, "alertas": alertas, "reporte": reporte}
