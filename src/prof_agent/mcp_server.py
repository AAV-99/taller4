"""Servidor MCP (bonificación): expone el RAG del corpus local, el temario, la lectura de páginas
oficiales y consultar_progreso.

Ejecutar (stdio):  uv run mcp_server
Probar con el inspector:  npx @modelcontextprotocol/inspector uv run mcp_server
"""
from mcp.server.fastmcp import FastMCP

from . import conocimiento
from .memory import MemoriaEstudiantes

mcp = FastMCP("prof_agent")


@mcp.tool()
def buscar_material(consulta: str) -> str:
    """Search the course documents (syllabus, Assignment 2) with RagTool. Write the query in English;
    results are in English and each fragment starts with its citation [Fuente: file.md § section]."""
    return conocimiento.buscar(consulta)


@mcp.tool()
def listar_material() -> str:
    """Lista las páginas oficiales del temario del curso FH1037 (id, título, URL y contenido)."""
    return conocimiento.listado_para_prompt(list(conocimiento.paginas()))


@mcp.tool()
def leer_material(pagina_id: str, inicio: int = 0, max_caracteres: int = 8000) -> str:
    """Lee una página del temario con ScrapeWebsiteTool (p. ej. 'py_control_flujo'), por partes."""
    if pagina_id not in conocimiento.paginas():
        return f"Página desconocida. Ids válidos: {', '.join(conocimiento.paginas())}"
    texto = conocimiento.leer(pagina_id)
    return f"{conocimiento.cita(pagina_id)}\n{texto[inicio:inicio + max_caracteres]}"


@mcp.tool()
def consultar_progreso(estudiante_id: str) -> str:
    """Devuelve notas, entregas, participación y memoria de tutorías de un estudiante (p. ej. 'alvaro_mutis')."""
    return conocimiento.progreso_estudiante(estudiante_id, MemoriaEstudiantes())


def main():
    mcp.run()


if __name__ == "__main__":
    main()
