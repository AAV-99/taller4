"""Herramientas del AgenteProfesor: recuperación RAG y consulta de progreso (LMS + memoria)."""
from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from . import rag
from .settings import cargar_lms, cargar_perfiles
from .memory import MemoriaEstudiantes
from .trace import registrar


def formatear_fragmentos(fragmentos: list[rag.Fragmento]) -> str:
    if not fragmentos:
        return "No se encontró material relevante en el corpus del curso."
    return "\n\n".join(f"{f.cita}\n{f.texto}" for f in fragmentos)


def progreso_estudiante(estudiante_id: str, memoria: MemoriaEstudiantes) -> str:
    perfil = cargar_perfiles().get(estudiante_id)
    lms = cargar_lms()["estudiantes"].get(estudiante_id)
    if not perfil or not lms:
        return f"No existe el estudiante '{estudiante_id}'. Ids válidos: {', '.join(cargar_perfiles())}."
    lineas = [f"Estudiante: {perfil['nombre']} ({perfil['perfil']})", "Entregas en el LMS:"]
    for e in lms["entregas"]:
        estado = f"nota {e['nota']}" if e["entregado"] else "NO ENTREGADO"
        fallos = f" · conceptos fallados: {', '.join(e['conceptos_fallados'])}" if e["conceptos_fallados"] else ""
        lineas.append(f"- {e['actividad']}: {estado}{fallos}")
    lineas.append(f"Último acceso: {lms['ultimo_acceso']} · mensajes en foro: {lms['mensajes_foro']}")
    lineas.append("Memoria de tutorías:\n" + memoria.resumen_para_tutor(estudiante_id))
    return "\n".join(lineas)


class BuscarMaterialInput(BaseModel):
    consulta: str = Field(..., description="Tema o pregunta a buscar en el material del curso")


class BuscarMaterialTool(BaseTool):
    name: str = "buscar_material"
    description: str = (
        "Busca en el corpus del curso (programa, slides, enunciado del taller, notebook) los fragmentos "
        "más relevantes para una consulta. Devuelve cada fragmento precedido de su cita "
        "[Fuente: archivo.md § sección], que debes copiar tal cual en tu respuesta."
    )
    args_schema: Type[BaseModel] = BuscarMaterialInput

    def _run(self, consulta: str) -> str:
        fragmentos = rag.buscar(consulta, k=3)
        registrar("tool_buscar_material", consulta=consulta, resultados=[f.cita for f in fragmentos])
        return formatear_fragmentos(fragmentos)


class ConsultarProgresoInput(BaseModel):
    estudiante_id: str = Field(..., description="Id del estudiante, p. ej. 'alvaro_mutis'")


class ConsultarProgresoTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "consultar_progreso"
    description: str = (
        "Consulta las notas, entregas y participación del estudiante en el LMS y el resumen de sus "
        "tutorías anteriores (memoria)."
    )
    args_schema: Type[BaseModel] = ConsultarProgresoInput
    memoria: MemoriaEstudiantes

    def _run(self, estudiante_id: str) -> str:
        registrar("tool_consultar_progreso", estudiante_id=estudiante_id)
        return progreso_estudiante(estudiante_id, self.memoria)
