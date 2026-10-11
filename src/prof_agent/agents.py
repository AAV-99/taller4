"""Construcción de los agentes a partir de config/agents.yaml y de los prompts de config/tasks.yaml."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent

from .guardrail import MAX_REINTENTOS, GuardrailPedagogico
from .memory import MemoriaEstudiantes
from .modelos import crear_llm
from .settings import MAX_RPM, VERBOSE, cargar_curso
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


def ejecutar_agente(agente: Agent, entrada: str, **kwargs):
    """Ejecuta `agente.kickoff`. Los errores de Gemini (429 por minuto o por día, 503) se resuelven solicitud por
    solicitud en el LLM (modelos.py), sin repetir el turno completo.

    Dentro de un event loop activo (Jupyter) CrewAI cambia a su modo asíncrono, que falla cuando el guardrail pide
    un reintento. Por eso, si hay un loop activo, el kickoff síncrono se ejecuta en un hilo aparte sin loop (el
    mismo camino que usan la consola y el Flow)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return agente.kickoff(entrada, **kwargs)
    with ThreadPoolExecutor(max_workers=1) as ejecutor:
        return ejecutor.submit(agente.kickoff, entrada, **kwargs).result()


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
    return _agente("estudiante", variables, llm=crear_llm(0.8, apoyo=True), max_iter=2)


def crear_evaluador() -> Agent:
    return _agente("evaluador", {}, llm=crear_llm(0.0, apoyo=True), max_iter=2)
