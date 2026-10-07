"""Servidor MCP (bonificación): expone buscar_material y consultar_progreso.

Ejecutar (stdio):  uv run mcp_server
Probar con el inspector:  npx @modelcontextprotocol/inspector uv run mcp_server
"""
from mcp.server.fastmcp import FastMCP

from . import rag
from .memory import MemoriaEstudiantes
from .tools import formatear_fragmentos, progreso_estudiante

mcp = FastMCP("prof_agent")


@mcp.tool()
def buscar_material(consulta: str, k: int = 3) -> str:
    """Busca en el corpus del curso FH1037 y devuelve fragmentos con su cita [Fuente: archivo.md § sección]."""
    return formatear_fragmentos(rag.buscar(consulta, k=k))


@mcp.tool()
def consultar_progreso(estudiante_id: str) -> str:
    """Devuelve notas, entregas, participación y memoria de tutorías de un estudiante (p. ej. 'alvaro_mutis')."""
    return progreso_estudiante(estudiante_id, MemoriaEstudiantes())


def main():
    mcp.run()


if __name__ == "__main__":
    main()
