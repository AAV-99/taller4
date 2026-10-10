"""Herramientas del AgenteProfesor.

1. buscar_material: RagTool (RAG oficial de crewai_tools) sobre el corpus local del curso
   (data/corpus/*.md, en INGLÉS): programa del curso y enunciado del Taller 2.
2. leer_<id>: una ScrapeWebsiteTool (crewai_tools) por página oficial del temario (data/temario.json).
3. consultar_progreso: notas y entregas del LMS simulado + memoria de tutorías.
4. search_docs / get_docs: servidor MCP externo y gratuito `python-docs-mcp-server`, que busca en
   TODA la documentación oficial de Python (índice local, sin API key). Se conecta con
   Agent(mcps=[MCPServerStdio(...)]), el soporte nativo de MCP de CrewAI.

El corpus está en inglés porque el modelo de embeddings local (ONNX all-MiniLM-L6-v2) funciona
mucho mejor en ese idioma: el agente consulta en inglés, recibe los fragmentos en inglés y los
traduce al español en su respuesta. Las versiones originales en español están en data/corpus/es/
(no se indexan).
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Type

from chromadb.config import Settings
from crewai.events import ToolUsageFinishedEvent, crewai_event_bus
from crewai.mcp import MCPServerStdio
from crewai.mcp.filters import create_static_tool_filter
from crewai.tools import BaseTool
from crewai_tools import RagTool, ScrapeWebsiteTool
from pydantic import BaseModel, ConfigDict, Field

from .memory import MemoriaEstudiantes
from .settings import CORPUS_DIR, ROOT, cargar_lms, cargar_perfiles, cargar_temario, registrar

# ===========================================================================
# 1. RAG del corpus local (RagTool)
# ===========================================================================
RAG_DB_DIR = ROOT / ".rag_db"
CHUNK_SIZE, CHUNK_OVERLAP = 900, 150
LIMITE_RESULTADOS = 3
UMBRAL_SIMILITUD = 0.2  # con 0.6 (valor por defecto de RagTool) quedan fuera fragmentos pertinentes


@dataclass
class Fragmento:
    fuente: str
    seccion: str
    texto: str

    @property
    def cita(self) -> str:
        return f"[Fuente: {self.fuente} § {self.seccion}]"


def _trocear(texto: str) -> list[str]:
    """Troceo recursivo (Taller 3 / clase 5): párrafos, luego líneas, con solapamiento entre trozos."""
    if len(texto) <= CHUNK_SIZE:
        return [texto]
    trozos, actual = [], ""
    for parte in re.split(r"(?<=\n)", texto):
        if len(actual) + len(parte) > CHUNK_SIZE and actual:
            trozos.append(actual.strip())
            actual = actual[-CHUNK_OVERLAP:]
        actual += parte
    if actual.strip():
        trozos.append(actual.strip())
    return trozos


@lru_cache
def cargar_fragmentos() -> list[Fragmento]:
    """Un fragmento por sección (## ...) de cada documento del corpus."""
    fragmentos = []
    for ruta in sorted(CORPUS_DIR.glob("*.md")):
        texto = ruta.read_text(encoding="utf-8")
        titulo_doc = texto.splitlines()[0].lstrip("# ").strip()
        for bloque in re.split(r"^(?=## )", texto, flags=re.M):
            lineas = bloque.strip().splitlines()
            if not lineas:
                continue
            seccion = lineas[0].lstrip("# ").strip() if lineas[0].startswith("## ") else "Introduction"
            for trozo in _trocear(bloque.strip()):
                fragmentos.append(Fragmento(ruta.name, seccion, f"{titulo_doc}\n{trozo}"))
    return fragmentos


def fuentes_corpus() -> set[str]:
    return {p.name for p in CORPUS_DIR.glob("*.md")}


@lru_cache
def herramienta_rag() -> RagTool:
    """RagTool compartido por todos los agentes; se reindexa desde cero una vez por proceso."""
    tool = RagTool(
        name="buscar_material",
        description=(
            "Course knowledge base written in ENGLISH: course syllabus (units, grading, tutoring policy, "
            "academic honesty) and Assignment 2 statement (exercises, required tests, rubric). ALWAYS write the "
            "query in English. Results come back in English: translate what you use into Spanish for the student "
            "and copy the citation [Fuente: file.md § section] exactly as it appears."
        ),
        similarity_threshold=UMBRAL_SIMILITUD,
        limit=LIMITE_RESULTADOS,
        config={
            # Embeddings ONNX locales: sin API key y sin gastar cuota de Gemini
            "embedding_model": {"provider": "onnx"},
            "vectordb": {
                "provider": "chromadb",
                # CrewAI siempre crea un PersistentClient: se fija la carpeta del proyecto (no ./chroma)
                "config": {"settings": Settings(persist_directory=str(RAG_DB_DIR), is_persistent=True,
                                                allow_reset=True, anonymized_telemetry=False)},
            },
        },
    )
    # Se vacía la colección antes de indexar para que no queden fragmentos de versiones anteriores
    cliente = tool.adapter._client
    cliente.delete_collection(collection_name=tool.collection_name)
    cliente.get_or_create_collection(collection_name=tool.collection_name)
    fragmentos = cargar_fragmentos()
    # RagTool descarta los metadatos al responder: la cita va dentro del texto de cada fragmento
    for f in fragmentos:
        tool.add(f"{f.cita}\n{f.texto}", data_type="text")
    registrar("rag_indexado", fragmentos=len(fragmentos), documentos=sorted(fuentes_corpus()))
    return tool


def buscar(consulta: str) -> str:
    """Consulta directa al RagTool (sin LLM), para la interfaz, el notebook y el servidor MCP."""
    return herramienta_rag().run(query=consulta)


# ===========================================================================
# 2. Documentación oficial (ScrapeWebsiteTool, una por página del temario)
# ===========================================================================
PREFIJO_TOOL = "leer_"


@lru_cache
def paginas() -> dict[str, dict]:
    return {p["id"]: p for p in cargar_temario()["paginas"]}


def normalizar_url(url: str) -> str:
    return url.split("#")[0].rstrip(".,;)/")


def urls_validas() -> set[str]:
    return {normalizar_url(p["url"]) for p in paginas().values()}


def cita(pagina_id: str) -> str:
    p = paginas()[pagina_id]
    return f"[Fuente: {p['titulo']} — {p['url']}]"


def crear_herramienta(pagina_id: str) -> ScrapeWebsiteTool:
    p = paginas()[pagina_id]
    tool = ScrapeWebsiteTool(website_url=p["url"], name=f"{PREFIJO_TOOL}{pagina_id}")
    # El constructor fija una descripción genérica; se reemplaza por el contenido de la página
    tool.description = f"Lee la página oficial «{p['titulo']}» ({p['url']}). Contenido: {p['contenido']}."
    tool._generate_description()
    return tool


def herramientas_docs() -> list[ScrapeWebsiteTool]:
    return [crear_herramienta(pid) for pid in paginas()]


def leer(pagina_id: str) -> str:
    """Lee una página sin LLM (para la interfaz y el servidor MCP)."""
    texto = crear_herramienta(pagina_id).run()
    registrar("lectura_directa", pagina=pagina_id, caracteres=len(texto))
    return texto


def listado_para_prompt(pagina_ids: list[str]) -> str:
    return "\n".join(
        f"- {PREFIJO_TOOL}{pid}: {paginas()[pid]['titulo']} ({paginas()[pid]['url']}) — {paginas()[pid]['contenido']}"
        for pid in pagina_ids
    )


# ===========================================================================
# 4. Servidor MCP externo: python-docs-mcp-server (toda la documentación oficial de Python)
# ===========================================================================
# Instalación (una vez):  uv tool install python-docs-mcp-server
#                         python-docs-mcp-server build-index --versions 3.13
# Va en su propio entorno porque exige mcp>=1.30 y crewai fija mcp<1.29.
MCP_PYTHON_DOCS_ACTIVO = os.getenv("PROF_AGENT_MCP_PYTHON_DOCS", "1") == "1"
VERSION_PYTHON_DOCS = "3.13"
HERRAMIENTAS_MCP = ["search_docs", "get_docs"]  # el servidor expone 6; el tutor solo necesita estas
URL_DOCS_PYTHON = "https://docs.python.org/"


def _parametros_mcp() -> tuple[str, list[str]]:
    # El ejecutable instalado con `uv tool install` arranca sin red; uvx consulta PyPI en cada arranque.
    # Se pasa el nombre (no la ruta completa): CrewAI lo usa para nombrar las herramientas y Gemini solo
    # acepta nombres cortos con letras, números, "_" y "-".
    if shutil.which("python-docs-mcp-server"):
        return "python-docs-mcp-server", ["serve"]
    return "uvx", ["python-docs-mcp-server", "serve"]


def servidor_mcp_python_docs() -> MCPServerStdio:
    comando, args = _parametros_mcp()
    return MCPServerStdio(
        command=comando,
        args=args,
        tool_filter=create_static_tool_filter(allowed_tool_names=HERRAMIENTAS_MCP),
        cache_tools_list=True,
    )


def servidores_mcp() -> list[MCPServerStdio]:
    return [servidor_mcp_python_docs()] if MCP_PYTHON_DOCS_ACTIVO else []


def instrucciones_mcp() -> str:
    """Bloque del prompt del tutor que explica el servidor MCP (vacío si está desactivado)."""
    if not MCP_PYTHON_DOCS_ACTIVO:
        return ""
    v = VERSION_PYTHON_DOCS
    return (
        f"- Servidor MCP python-docs (herramientas ...search_docs y ...get_docs): busca en TODA la documentación "
        f"oficial de Python {v}, en inglés. Úsalo solo si la duda es sobre una función o tema que NO está en las "
        f"páginas sugeridas (p. ej. round, sorted, dict.get). Primero search_docs(query, version=\"{v}\") y luego "
        f"get_docs(slug, anchor, version=\"{v}\", max_chars=1500) con el anchor de un resultado. El slug va SIN "
        f"\".html\": \"library/stdtypes\", no \"library/stdtypes.html\". Para funciones integradas (round, len, "
        f"sorted...) el slug es \"library/functions\" aunque search_docs diga \"builtins/functions.html\". "
        f"Traduce al español y cita [Fuente: Python {v} docs — https://docs.python.org/{v}/<slug>.html#<anchor>]."
    )


def consultar_mcp_python_docs(herramienta: str, argumentos: dict) -> str:
    """Llama al servidor MCP sin LLM (interfaz y notebook). Corre en otro hilo para funcionar
    también dentro de Jupyter o Streamlit, que pueden tener un event loop activo."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    comando, args = _parametros_mcp()

    async def _llamar() -> str:
        async with stdio_client(StdioServerParameters(command=comando, args=args)) as (leer_, escribir):
            async with ClientSession(leer_, escribir) as sesion:
                await sesion.initialize()
                resultado = await sesion.call_tool(herramienta, argumentos)
                return "\n".join(getattr(c, "text", "") for c in resultado.content)

    with ThreadPoolExecutor(max_workers=1) as ejecutor:
        texto = ejecutor.submit(asyncio.run, _llamar()).result()
    registrar("mcp_directo", herramienta=herramienta, argumentos=argumentos, caracteres=len(texto))
    return texto


def es_fuente_valida(fuente: str) -> bool:
    """Lo que el guardrail acepta como cita: archivos del corpus local, URLs del temario o cualquier
    página de la documentación oficial de Python (lo que devuelve el servidor MCP)."""
    return fuente in fuentes_corpus() or fuente in urls_validas() or fuente.startswith(URL_DOCS_PYTHON)


# ===========================================================================
# 3. Progreso del estudiante (LMS simulado + memoria)
# ===========================================================================
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


# ===========================================================================
# Traza del uso de herramientas (evento oficial de CrewAI)
# ===========================================================================
@crewai_event_bus.on(ToolUsageFinishedEvent)
def _registrar_uso_herramienta(source, event: ToolUsageFinishedEvent) -> None:
    args = event.tool_args if isinstance(event.tool_args, dict) else {}
    registrar(
        "tool_uso",
        herramienta=event.tool_name,
        agente=(event.agent_role or "").split("—")[0].strip(),
        consulta=args.get("query"),  # en buscar_material debe venir en inglés
        caracteres=len(str(event.output or "")),
        desde_cache=event.from_cache,
    )
