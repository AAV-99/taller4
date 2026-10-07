"""Traza de ejecución en JSONL (logs/trace.jsonl): cada mensaje, consulta RAG y guardrail."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from .settings import LOGS_DIR

TRACE_FILE = LOGS_DIR / "trace.jsonl"
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
    print(f"[TRACE] {evento}: " + json.dumps(datos, ensure_ascii=True)[:300], flush=True)
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
