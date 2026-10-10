"""Configuración compartida: rutas, carga de datos, LLM y traza de ejecución (logs/trace.jsonl)."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from crewai import LLM
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
MEMORY_DIR = ROOT / "memory"
LOGS_DIR = ROOT / "logs"
TRACE_FILE = LOGS_DIR / "trace.jsonl"

load_dotenv(ROOT / ".env")

# Plan gratuito de Gemini: ~20 solicitudes/día POR MODELO. El tutor usa MODEL y los agentes de apoyo
# (estudiante, monitor, evaluador) usan MODEL_APOYO, un modelo lite con cuota independiente.
MODEL = os.getenv("MODEL", "gemini/gemini-3.5-flash")
MODEL_APOYO = os.getenv("MODEL_APOYO", "gemini/gemini-3.5-flash-lite")
# Límite de solicitudes por minuto por agente (plan gratuito de Gemini: 5 RPM)
MAX_RPM = int(os.getenv("PROF_AGENT_MAX_RPM", "4"))


def crear_llm(temperature: float = 0.3, modelo: str = MODEL) -> LLM:
    # max_tokens incluye los tokens de razonamiento de Gemini; con valores bajos la respuesta se corta.
    return LLM(model=modelo, temperature=temperature, max_tokens=8000, max_retries=4, timeout=120)


def api_key_configurada() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


# ---------------------------------------------------------------------------
# Datos (data/*.json)
# ---------------------------------------------------------------------------
def _leer_json(nombre: str):
    return json.loads((DATA_DIR / nombre).read_text(encoding="utf-8"))


@lru_cache
def cargar_perfiles() -> dict[str, dict]:
    """Perfiles de estudiante indexados por id (definidos como datos, no en los prompts)."""
    return {e["id"]: e for e in _leer_json("perfiles.json")["estudiantes"]}


@lru_cache
def cargar_curso() -> dict:
    return _leer_json("perfiles.json")["curso"]


@lru_cache
def cargar_actividades() -> dict[str, dict]:
    return {a["id"]: a for a in _leer_json("actividades.json")}


@lru_cache
def cargar_temario() -> dict:
    """Unidades del curso y lista predeterminada de páginas oficiales que puede leer el tutor."""
    return _leer_json("temario.json")


@lru_cache
def cargar_lms() -> dict:
    return _leer_json("lms.json")


# ---------------------------------------------------------------------------
# Traza de ejecución: cada mensaje, herramienta usada, guardrail, monitor y juez, agrupados por run_id
# ---------------------------------------------------------------------------
# Variable de módulo (no ContextVar): el Flow ejecuta cada método en un hilo distinto
_run_id = "sin-run"


def nuevo_run(prefijo: str) -> str:
    return fijar_run(f"{prefijo}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}")


def fijar_run(run_id: str) -> str:
    global _run_id
    _run_id = run_id
    return run_id


def run_actual() -> str:
    return _run_id


def registrar(evento: str, **datos) -> None:
    registro = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "run_id": _run_id,
        "evento": evento,
        **datos,
    }
    # stderr: en el servidor MCP (stdio) la salida estándar es el canal del protocolo JSON-RPC
    print(f"[TRACE] {evento}: " + json.dumps(datos, ensure_ascii=True)[:300], file=sys.stderr, flush=True)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        pass  # la traza nunca debe tumbar la corrida


def leer_traza(run_id: str | None = None) -> list[dict]:
    if not TRACE_FILE.exists():
        return []
    eventos = [json.loads(l) for l in TRACE_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [e for e in eventos if run_id is None or e["run_id"] == run_id]
