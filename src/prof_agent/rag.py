"""Recuperación sobre el corpus del curso.

Reutiliza el pipeline del Taller 3 / clase 5: troceo recursivo por caracteres que
conserva metadatos (documento y sección) + recuperación dispersa BM25 con un
tokenizador que preserva tokens técnicos (`range()`, `dic.items`, `3.0`).
Se omite la parte densa (FAISS + embeddings) para que el prototipo corra sin GPU
ni descargas de modelos; el corpus es pequeño y BM25 basta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from rank_bm25 import BM25Okapi

from .settings import CORPUS_DIR

CHUNK_SIZE, CHUNK_OVERLAP = 900, 150

STOPWORDS = set(
    "a al algo como con cual de del el en es esta este la las lo los mas me mi no o para pero "
    "por que se si sin sobre su sus un una uno y ya yo tu te le les hay ser son cómo qué cuál "
    "the of and to in is".split()
)


@dataclass
class Fragmento:
    fuente: str
    seccion: str
    texto: str
    score: float = 0.0

    @property
    def cita(self) -> str:
        return f"[Fuente: {self.fuente} § {self.seccion}]"


def tokenizar(texto: str) -> list[str]:
    tokens = re.findall(r"[a-záéíóúñü0-9_]+(?:[./-][a-záéíóúñü0-9_]+)*", texto.lower())
    return [t for t in tokens if t not in STOPWORDS]


def _trocear(texto: str) -> list[str]:
    """Troceo recursivo: párrafos, luego líneas, con solapamiento entre trozos."""
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
    fragmentos = []
    for ruta in sorted(CORPUS_DIR.glob("*.md")):
        texto = ruta.read_text(encoding="utf-8")
        titulo_doc = texto.splitlines()[0].lstrip("# ").strip()
        # Cada sección "## ..." es una unidad de recuperación con su propio título
        for bloque in re.split(r"^(?=## )", texto, flags=re.M):
            lineas = bloque.strip().splitlines()
            if not lineas:
                continue
            seccion = lineas[0].lstrip("# ").strip() if lineas[0].startswith("## ") else "Introducción"
            for trozo in _trocear(bloque.strip()):
                # Se antepone el título del documento para que BM25 lo considere
                fragmentos.append(Fragmento(ruta.name, seccion, f"{titulo_doc}\n{trozo}"))
    return fragmentos


@lru_cache
def _indice() -> BM25Okapi:
    return BM25Okapi([tokenizar(f.texto) for f in cargar_fragmentos()])


def buscar(consulta: str, k: int = 3) -> list[Fragmento]:
    fragmentos = cargar_fragmentos()
    scores = _indice().get_scores(tokenizar(consulta))
    orden = sorted(range(len(fragmentos)), key=lambda i: -scores[i])[:k]
    return [
        Fragmento(fragmentos[i].fuente, fragmentos[i].seccion, fragmentos[i].texto, float(scores[i]))
        for i in orden
        if scores[i] > 0
    ]


def fuentes_validas() -> set[str]:
    return {p.name for p in CORPUS_DIR.glob("*.md")}
