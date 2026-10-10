#!/usr/bin/env python
"""Flow de CrewAI que orquesta el escenario 3 (acompañamiento sin entregar la respuesta)."""
import os
import signal
from pathlib import Path

from crewai.flow import Flow, listen, start
from pydantic import BaseModel

from .acompanamiento import simular_acompanamiento
from .conocimiento import cargar_fragmentos, paginas
from .memory import MemoriaEstudiantes
from .settings import MEMORY_DIR, VERBOSE, cargar_actividades, cargar_perfiles, nuevo_run, registrar


class ProfAgentState(BaseModel):
    estudiante_id: str = "kevin_genez"
    actividad_id: str = "taller2_ej3"
    turnos: int = 2
    memoria_dir: str = str(MEMORY_DIR)
    run_id: str = ""
    transcripcion: str = ""


class ProfAgentFlow(Flow[ProfAgentState]):

    @start()
    def inicializar(self):
        if self.state.estudiante_id not in cargar_perfiles():
            raise ValueError(f"Estudiante '{self.state.estudiante_id}' no existe en data/perfiles.json")
        if self.state.actividad_id not in cargar_actividades():
            raise ValueError(f"Actividad '{self.state.actividad_id}' no existe en data/actividades.json")
        self.state.run_id = nuevo_run("acompanamiento")
        registrar("flow_inicio", estudiante=self.state.estudiante_id, actividad=self.state.actividad_id,
                  turnos=self.state.turnos, fragmentos_corpus=len(cargar_fragmentos()),
                  paginas_temario=len(paginas()))

    @listen(inicializar)
    def acompanar(self):
        resultado = simular_acompanamiento(
            self.state.estudiante_id, self.state.actividad_id, self.state.turnos,
            MemoriaEstudiantes(Path(self.state.memoria_dir)),
        )
        self.state.transcripcion = resultado["markdown"]


def _salida_inmediata(signum, frame):
    # Ctrl+C solo interrumpe el hilo principal; os._exit corta también las llamadas al LLM.
    print("\n[prof_agent] Interrumpido.", flush=True)
    os._exit(130)


def ejecutar(**inputs) -> ProfAgentState:
    # suppress_flow_events silencia los paneles del Flow en consola (la traza queda en logs/trace.jsonl)
    flow = ProfAgentFlow(suppress_flow_events=not VERBOSE)
    flow.kickoff(inputs=inputs)
    registrar("flow_fin", estudiante=flow.state.estudiante_id)
    return flow.state


def kickoff():
    signal.signal(signal.SIGINT, _salida_inmediata)
    signal.signal(signal.SIGTERM, _salida_inmediata)
    print("\n" + ejecutar().transcripcion)


def plot():
    ProfAgentFlow().plot("prof_agent_flow")


def run_with_trigger():
    """Ejecuta el flow con un payload JSON, p. ej. {"estudiante_id": "alvaro_mutis", "actividad_id": "taller2_ej1"}."""
    import json
    import sys

    if len(sys.argv) < 2:
        raise Exception("No se recibió payload. Pase un JSON como argumento.")
    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Payload JSON inválido")
    # No se devuelve el estado: el script de consola lo usaría como código de salida
    print(ejecutar(**payload).transcripcion)


if __name__ == "__main__":
    kickoff()
