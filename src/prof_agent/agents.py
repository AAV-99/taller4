"""Construcción de los agentes a partir de config/agents.yaml y de los prompts de config/tasks.yaml."""
from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent

from .guardrail import MAX_REINTENTOS, GuardrailPedagogico
from .memory import MemoriaEstudiantes
from .settings import MAX_RPM, MODEL_APOYO, cargar_curso, crear_llm
from .conocimiento import ConsultarProgresoTool, herramienta_rag, herramientas_docs, servidores_mcp

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
        verbose=True,
        **kwargs,
    )


ESPERAS_503 = (5, 15, 30)


def ejecutar_agente(agente: Agent, entrada: str, **kwargs):
    """`agente.kickoff` con reintentos cuando Gemini responde 503 (modelo saturado, suele ser temporal)."""
    for espera in (*ESPERAS_503, None):
        try:
            return agente.kickoff(entrada, **kwargs)
        except Exception as exc:
            if espera is None or not ("503" in str(exc) or "UNAVAILABLE" in str(exc)):
                raise
            print(f"[prof_agent] Gemini saturado (503); reintento en {espera} s", flush=True)
            time.sleep(espera)


def prompt(tarea: str, **variables) -> str:
    cfg = _yaml("tasks.yaml")[tarea]
    return f"{cfg['description'].format(**variables)}\nRESULTADO ESPERADO: {cfg['expected_output'].strip()}"


def crear_profesor(memoria: MemoriaEstudiantes, guardrail: GuardrailPedagogico) -> Agent:
    return _agente(
        "profesor",
        {},
        llm=crear_llm(0.4),
        # RagTool del corpus local + una ScrapeWebsiteTool por página oficial del temario (leer_<id>) + progreso
        tools=[herramienta_rag(), *herramientas_docs(), ConsultarProgresoTool(memoria=memoria)],
        # Servidor MCP externo python-docs-mcp-server: search_docs y get_docs (toda la doc. oficial de Python)
        mcps=servidores_mcp(),
        guardrail=guardrail.como_funcion(),
        guardrail_max_retries=MAX_REINTENTOS,
        max_iter=5,
    )


def crear_estudiante(perfil: dict) -> Agent:
    variables = {**perfil, "errores_frecuentes": "; ".join(perfil["errores_frecuentes"])}
    return _agente("estudiante", variables, llm=crear_llm(0.8, MODEL_APOYO), max_iter=2)


def crear_monitor() -> Agent:
    return _agente("monitor", {}, llm=crear_llm(0.2, MODEL_APOYO), max_iter=2)


def crear_evaluador() -> Agent:
    return _agente("evaluador", {}, llm=crear_llm(0.0, MODEL_APOYO), max_iter=2)
