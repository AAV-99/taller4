"""Memoria por estudiante: un archivo JSON por estudiante en memory/.

Guarda el historial de interacciones, los conceptos con dificultad, el nivel de
pista alcanzado por actividad y los intentos de obtener la solución. El tutor
recibe un resumen de esta memoria en cada interacción.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .settings import MEMORY_DIR

NIVEL_MAXIMO_PISTA = 3

# Conceptos detectados por palabras clave en los mensajes del estudiante
CONCEPTOS = {
    "return vs print": [r"\breturn\b", r"\bprint\b", r"\bnone\b"],
    "acumuladores": [r"acumulador", r"\btotal\s*[+=]", r"\bsuma\b"],
    "ciclos": [r"\bfor\b", r"\bwhile\b", r"\brange\b", r"\bciclo"],
    "diccionarios": [r"diccionario", r"\bdict\b", r"keyerror", r"\.items\(", r"\bclave"],
    "listas e índices": [r"\blista", r"indexerror", r"[ií]ndice", r"\bappend\b"],
    "indentación": [r"indent"],
    "casos borde": [r"vac[ií]a", r"zerodivision", r"caso borde"],
}


def detectar_conceptos(texto: str) -> list[str]:
    texto = texto.lower()
    return [c for c, patrones in CONCEPTOS.items() if any(re.search(p, texto) for p in patrones)]


class MemoriaEstudiantes:
    def __init__(self, base_dir: Path = MEMORY_DIR):
        self.base_dir = Path(base_dir)

    def _ruta(self, estudiante_id: str) -> Path:
        return self.base_dir / f"{estudiante_id}.json"

    def cargar(self, estudiante_id: str) -> dict:
        ruta = self._ruta(estudiante_id)
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
        return {
            "estudiante_id": estudiante_id,
            "interacciones": [],
            "actividades": {},
            "conceptos_dificultad": {},
            "intentos_obtener_solucion": 0,
        }

    def guardar(self, estudiante_id: str, memoria: dict) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._ruta(estudiante_id).write_text(json.dumps(memoria, ensure_ascii=False, indent=2), encoding="utf-8")

    def nivel_pista(self, estudiante_id: str, actividad: str) -> int:
        """La pista sube un nivel por cada turno previo en la misma actividad (máximo 3)."""
        turnos = self.cargar(estudiante_id)["actividades"].get(actividad, {}).get("turnos", 0)
        return min(NIVEL_MAXIMO_PISTA, turnos + 1)

    def registrar_interaccion(
        self,
        estudiante_id: str,
        *,
        escenario: str,
        actividad: str,
        mensaje: str,
        respuesta: str,
        fuentes: list[str],
        nivel_pista: int,
        intento_obtener_solucion: bool,
        guardrail: str,
        run_id: str,
    ) -> dict:
        memoria = self.cargar(estudiante_id)
        memoria["interacciones"].append(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "run_id": run_id,
                "escenario": escenario,
                "actividad": actividad,
                "mensaje_estudiante": mensaje,
                "respuesta_tutor": respuesta,
                "fuentes": fuentes,
                "nivel_pista": nivel_pista,
                "intento_obtener_solucion": intento_obtener_solucion,
                "guardrail": guardrail,
            }
        )
        # Pedir la solución no cuenta como avance: no sube el nivel de pista
        if not intento_obtener_solucion:
            act = memoria["actividades"].setdefault(actividad, {"turnos": 0})
            act["turnos"] += 1
        else:
            memoria["intentos_obtener_solucion"] += 1
        for concepto in detectar_conceptos(mensaje):
            memoria["conceptos_dificultad"][concepto] = memoria["conceptos_dificultad"].get(concepto, 0) + 1
        self.guardar(estudiante_id, memoria)
        return memoria

    def resumen_para_tutor(self, estudiante_id: str, ultimas: int = 4) -> str:
        memoria = self.cargar(estudiante_id)
        if not memoria["interacciones"]:
            return "Sin interacciones previas con este estudiante."
        lineas = [f"Interacciones previas: {len(memoria['interacciones'])}."]
        if memoria["conceptos_dificultad"]:
            conceptos = sorted(memoria["conceptos_dificultad"].items(), key=lambda x: -x[1])
            lineas.append("Conceptos con dificultad (veces): " + ", ".join(f"{c} ({n})" for c, n in conceptos))
        if memoria["intentos_obtener_solucion"]:
            lineas.append(f"Veces que ha pedido la solución completa: {memoria['intentos_obtener_solucion']}.")
        lineas.append("Últimas interacciones:")
        for it in memoria["interacciones"][-ultimas:]:
            lineas.append(
                f"- [{it['ts'][:16]} · {it['actividad']} · pista nivel {it['nivel_pista']}] "
                f"Estudiante: {it['mensaje_estudiante'][:220]!r} | Tutor: {it['respuesta_tutor'][:220]!r}"
            )
        return "\n".join(lineas)

    def reiniciar(self, estudiante_id: str | None = None) -> None:
        if estudiante_id is None:
            shutil.rmtree(self.base_dir, ignore_errors=True)
        else:
            self._ruta(estudiante_id).unlink(missing_ok=True)
