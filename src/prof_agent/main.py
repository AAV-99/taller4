#!/usr/bin/env python
"""Flow de CrewAI que orquesta los escenarios del Sistema Tutorial Inteligente."""
import os
import signal
from pathlib import Path

from crewai.flow import Flow, listen, router, start
from pydantic import BaseModel

from . import rag
from .memory import MemoriaEstudiantes
from .monitor import ejecutar_monitor
from .scenarios import simular_acompanamiento
from .settings import MEMORY_DIR, cargar_perfiles
from .trace import nuevo_run, registrar

ESCENARIOS = ("acompanamiento", "seguimiento", "demo")


class ProfAgentState(BaseModel):
    escenario: str = "demo"
    estudiante_id: str = "kevin_genez"
    actividad_id: str = "taller2_ej3"
    turnos: int = 3
    memoria_dir: str = str(MEMORY_DIR)
    run_id: str = ""
    transcripcion: str = ""
    reporte_monitor: str = ""
    alertas: list[dict] = []


class ProfAgentFlow(Flow[ProfAgentState]):

    @start()
    def inicializar(self):
        if self.state.escenario not in ESCENARIOS:
            raise ValueError(f"Escenario '{self.state.escenario}' inválido; use uno de {ESCENARIOS}")
        if self.state.estudiante_id not in cargar_perfiles():
            raise ValueError(f"Estudiante '{self.state.estudiante_id}' no existe en data/perfiles.json")
        self.state.run_id = nuevo_run(self.state.escenario)
        n = len(rag.cargar_fragmentos())
        registrar("flow_inicio", escenario=self.state.escenario, estudiante=self.state.estudiante_id,
                  actividad=self.state.actividad_id, fragmentos_corpus=n)

    @router(inicializar)
    def elegir_escenario(self):
        return self.state.escenario

    def _memoria(self) -> MemoriaEstudiantes:
        return MemoriaEstudiantes(Path(self.state.memoria_dir))

    def _acompanamiento(self):
        resultado = simular_acompanamiento(
            self.state.estudiante_id, self.state.actividad_id, self.state.turnos, self._memoria()
        )
        self.state.transcripcion = resultado["markdown"]

    def _seguimiento(self):
        resultado = ejecutar_monitor(self._memoria())
        self.state.reporte_monitor = resultado["reporte"]
        self.state.alertas = resultado["alertas"]

    @listen("acompanamiento")
    def handle_acompanamiento(self):
        self._acompanamiento()

    @listen("seguimiento")
    def handle_seguimiento(self):
        self._seguimiento()

    @listen("demo")
    def handle_demo(self):
        # Escenario 3 primero: sus interacciones alimentan la memoria que lee el monitor
        self._acompanamiento()
        self._seguimiento()


def _salida_inmediata(signum, frame):
    # Ctrl+C solo interrumpe el hilo principal; os._exit corta también las llamadas al LLM.
    print("\n[prof_agent] Interrumpido.", flush=True)
    os._exit(130)


def ejecutar(**inputs) -> ProfAgentState:
    flow = ProfAgentFlow()
    flow.kickoff(inputs=inputs)
    registrar("flow_fin", escenario=flow.state.escenario)
    return flow.state


def kickoff():
    signal.signal(signal.SIGINT, _salida_inmediata)
    signal.signal(signal.SIGTERM, _salida_inmediata)
    estado = ejecutar(escenario=os.getenv("ESCENARIO", "demo"))
    if estado.transcripcion:
        print("\n" + estado.transcripcion)
    if estado.reporte_monitor:
        print("\n" + estado.reporte_monitor)


def plot():
    ProfAgentFlow().plot("prof_agent_flow")


def run_with_trigger():
    """Ejecuta el flow con un payload JSON, p. ej. {"escenario": "acompanamiento", "estudiante_id": "alvaro_mutis"}."""
    import json
    import sys

    if len(sys.argv) < 2:
        raise Exception("No se recibió payload. Pase un JSON como argumento.")
    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Payload JSON inválido")
    # No se devuelve el estado: el script de consola lo usaría como código de salida
    estado = ejecutar(**payload)
    print(estado.transcripcion or estado.reporte_monitor)


if __name__ == "__main__":
    kickoff()
