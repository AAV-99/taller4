"""Construcción de los agentes a partir de config/agents.yaml y de los prompts de config/tasks.yaml."""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent

from .guardrail import MAX_REINTENTOS, GuardrailPedagogico
from .memory import MemoriaEstudiantes
from .settings import MAX_RPM, MODEL_APOYO, MODELOS_RESPALDO, VERBOSE, cargar_curso, crear_llm, registrar
from .conocimiento import herramienta_rag, herramientas_docs, servidores_mcp

CONFIG_DIR = Path(__file__).resolve().parent / "config"


@lru_cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / nombre).read_text(encoding="utf-8"))


def _curso() -> str:
    curso = cargar_curso()
    return f"{curso['codigo']} {curso['nombre']}"


def _agente(nombre: str, variables: dict, **kwargs) -> Agent:
    cfg = _yaml("agents.yaml")[nombre]
    variables = {"curso": _curso(), **variables}
    return Agent(
        role=cfg["role"].strip().format(**variables),
        goal=cfg["goal"].strip().format(**variables),
        backstory=cfg["backstory"].strip().format(**variables),
        max_rpm=MAX_RPM,
        verbose=VERBOSE,
        **kwargs,
    )


ESPERAS_503 = (5, 15, 30)
# Modelos que ya devolvieron 429 (cuota diaria agotada) en este proceso: se saltan en los turnos siguientes
_MODELOS_AGOTADOS: set[str] = set()


def _kickoff(agente: Agent, entrada: str, **kwargs):
    """Dentro de un event loop activo (Jupyter) CrewAI cambia a su modo asíncrono, que falla cuando el
    guardrail pide un reintento. Por eso, si hay un loop activo, el kickoff síncrono se ejecuta en un hilo
    aparte sin loop (el mismo camino que usan la consola y el Flow)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return agente.kickoff(entrada, **kwargs)
    with ThreadPoolExecutor(max_workers=1) as ejecutor:
        return ejecutor.submit(agente.kickoff, entrada, **kwargs).result()


def _cuota_agotada(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


def _saturado(exc: Exception) -> bool:
    return "503" in str(exc) or "UNAVAILABLE" in str(exc)


def ejecutar_agente(agente: Agent, entrada: str, **kwargs):
    """`agente.kickoff` con dos protecciones para el plan gratuito de Gemini:
    - 503 (modelo saturado, suele ser temporal): reintenta con espera creciente.
    - 429 (cuota diaria agotada) o 503 que persiste tras los reintentos: pasa al siguiente modelo de la cadena
      MODELOS_RESPALDO (con reintentos nuevos) y vuelve a intentar."""
    esperas = list(ESPERAS_503)
    pendientes = [m for m in MODELOS_RESPALDO
                  if m.split("/")[-1] != agente.llm.model and m.split("/")[-1] not in _MODELOS_AGOTADOS]
    if agente.llm.model in _MODELOS_AGOTADOS and pendientes:
        agente.llm = crear_llm(agente.llm.temperature, pendientes.pop(0))
    while True:
        try:
            return _kickoff(agente, entrada, **kwargs)
        except Exception as exc:
            if esperas and _saturado(exc):
                espera = esperas.pop(0)
                print(f"[prof_agent] Gemini saturado (503); reintento en {espera} s", flush=True)
                time.sleep(espera)
                continue
            if _cuota_agotada(exc):
                _MODELOS_AGOTADOS.add(agente.llm.model)
            if (_cuota_agotada(exc) or _saturado(exc)) and pendientes:
                anterior, siguiente = agente.llm.model, pendientes.pop(0)
                agente.llm = crear_llm(agente.llm.temperature, siguiente)
                registrar("cambio_modelo", agente=agente.role.split("—")[0].strip(), de=anterior, a=siguiente,
                          motivo="429 cuota" if _cuota_agotada(exc) else "503 persistente")
                esperas = list(ESPERAS_503)
                continue
            raise


def prompt(tarea: str, **variables) -> str:
    cfg = _yaml("tasks.yaml")[tarea]
    return f"{cfg['description'].format(**variables)}\nRESULTADO ESPERADO: {cfg['expected_output'].strip()}"


def crear_profesor(memoria: MemoriaEstudiantes, guardrail: GuardrailPedagogico) -> Agent:
    return _agente(
        "profesor",
        {},
        llm=crear_llm(0.4),
        # RagTool del corpus local + una ScrapeWebsiteTool por página oficial del temario (leer_<id>)
        tools=[herramienta_rag(), *herramientas_docs()],
        # Servidor MCP externo python-docs-mcp-server: search_docs y get_docs (toda la doc. oficial de Python)
        mcps=servidores_mcp(),
        guardrail=guardrail.como_funcion(),
        guardrail_max_retries=MAX_REINTENTOS,
        max_iter=5,
    )


def crear_estudiante(perfil: dict) -> Agent:
    variables = {**perfil, "errores_frecuentes": "; ".join(perfil["errores_frecuentes"])}
    return _agente("estudiante", variables, llm=crear_llm(0.8, MODEL_APOYO), max_iter=2)


def crear_evaluador() -> Agent:
    return _agente("evaluador", {}, llm=crear_llm(0.0, MODEL_APOYO), max_iter=2)
