"""Rutas, carga de datos y LLM compartidos por todo el proyecto."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from crewai import LLM
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
MEMORY_DIR = ROOT / "memory"
LOGS_DIR = ROOT / "logs"

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
def cargar_lms() -> dict:
    return _leer_json("lms.json")
