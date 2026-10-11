"""LLM de Gemini con cadena de modelos de respaldo POR SOLICITUD (basado en VDI-streamlit/modelos.py).

El plan gratuito de Gemini tiene una cuota diaria POR MODELO y un límite por minuto. Cada solicitud al LLM
se protege así, sin repetir el resto del turno del agente (herramientas ya usadas, etc.):

- 429 por minuto: espera lo que indica Gemini (retryDelay) y reintenta con el MISMO modelo.
- 429 por día: marca el modelo como agotado y repite la solicitud con el siguiente de la cadena. Los
  agotados se saltan durante el resto del proceso, en todos los agentes.
- 503 (modelo saturado, temporal): reintenta con espera creciente y, si persiste, pasa al siguiente modelo
  solo para esa solicitud (no se marca como agotado).

Se sobrescriben call y acall, así funciona igual en modo síncrono y asíncrono.
"""
from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from crewai.llms.providers.gemini.completion import GeminiCompletion

from .settings import MODEL, MODEL_APOYO, MODELOS_RESPALDO, registrar

ESPERAS_503 = (5, 15, 30)
ESPERA_POR_MINUTO_S = 60  # si Gemini no indica cuánto esperar
MAX_ESPERAS_POR_MINUTO = 3  # después se trata como cuota agotada y se cambia de modelo

# Modelos que ya devolvieron 429 por cuota diaria en este proceso. Común a todos los agentes.
_AGOTADOS: set[str] = set()


class CuotaAgotadaError(RuntimeError):
    """Ningún modelo de la cadena está disponible. No es un error temporal: se detiene la ejecución."""


def _sin_proveedor(modelo: str) -> str:
    return modelo.split("/")[-1]


def _es_429(error: Exception) -> bool:
    texto = str(error)
    return getattr(error, "code", None) == 429 or "429" in texto or "RESOURCE_EXHAUSTED" in texto


def _es_503(error: Exception) -> bool:
    texto = str(error)
    return getattr(error, "code", None) == 503 or "503" in texto or "UNAVAILABLE" in texto


def _es_limite_por_minuto(error: Exception) -> bool:
    texto = str(error)
    return "PerMinute" in texto and "PerDay" not in texto


def _segundos_de_espera(error: Exception) -> float:
    encontrado = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", str(error))
    return float(encontrado.group(1)) + 1 if encontrado else ESPERA_POR_MINUTO_S


class GeminiConRespaldo(GeminiCompletion):
    """GeminiCompletion de CrewAI que cambia de modelo cuando el actual agota su cuota o sigue saturado."""

    cadena: list[str] = []

    # --- Decisión común a call y acall -------------------------------------------------------------
    def _decidir(self, error: Exception, estado: dict) -> float | None:
        """Segundos a esperar antes de reintentar (0 = reintentar ya con otro modelo); None si no queda ningún
        modelo disponible. Los errores que no son 429 ni 503 se relanzan tal cual."""
        if _es_429(error):
            if _es_limite_por_minuto(error) and estado["esperas_minuto"] < MAX_ESPERAS_POR_MINUTO:
                estado["esperas_minuto"] += 1
                espera = _segundos_de_espera(error)
                print(f"[prof_agent] Límite por minuto de {self.model} (429); reintento en {espera:.0f} s", flush=True)
                return espera
            _AGOTADOS.add(self.model)
            return 0 if self._cambiar_de_modelo("429 cuota diaria", estado) else None
        if _es_503(error):
            if estado["esperas_503"]:
                espera = estado["esperas_503"].pop(0)
                print(f"[prof_agent] {self.model} saturado (503); reintento en {espera} s", flush=True)
                return espera
            estado["saturados"].add(self.model)
            return 0 if self._cambiar_de_modelo("503 persistente", estado) else None
        raise error

    def _cambiar_de_modelo(self, motivo: str, estado: dict) -> bool:
        """Pasa al siguiente modelo disponible de la cadena; False si no queda ninguno."""
        anterior = self.model
        pendientes = [m for m in self.cadena if m not in _AGOTADOS and m not in estado["saturados"]]
        if not pendientes:
            return False
        self.model = pendientes[0]
        estado["esperas_minuto"], estado["esperas_503"] = 0, list(ESPERAS_503)
        registrar("cambio_modelo", de=anterior, a=self.model, motivo=motivo)
        print(f"[prof_agent] {anterior} ({motivo}); se continúa con {self.model}", flush=True)
        return True

    def _sin_modelos(self) -> CuotaAgotadaError:
        return CuotaAgotadaError(
            f"Ningún modelo de Gemini disponible ({', '.join(self.cadena)}): cuota diaria agotada o modelos "
            "saturados. Intenta de nuevo más tarde o cambia MODEL / MODEL_RESPALDO en .env."
        )

    def _estado_inicial(self) -> dict:
        estado = {"esperas_minuto": 0, "esperas_503": list(ESPERAS_503), "saturados": set()}
        if self.model in _AGOTADOS and not self._cambiar_de_modelo("agotado antes en este proceso", estado):
            raise self._sin_modelos()
        return estado

    # El error final se lanza FUERA del except: si llevara el 429 original en __context__, el reintento
    # automático de CrewAI lo tomaría por un límite temporal y repetiría la llamada en vano.
    def _intentar(self, operacion: Callable[[], Any]) -> Any:
        estado = self._estado_inicial()
        while True:
            try:
                return operacion()
            except Exception as error:
                espera = self._decidir(error, estado)
            if espera is None:
                raise self._sin_modelos()
            if espera:
                time.sleep(espera)

    async def _aintentar(self, operacion: Callable[[], Awaitable[Any]]) -> Any:
        estado = self._estado_inicial()
        while True:
            try:
                return await operacion()
            except Exception as error:
                espera = self._decidir(error, estado)
            if espera is None:
                raise self._sin_modelos()
            if espera:
                await asyncio.sleep(espera)

    # --- Métodos que usa CrewAI --------------------------------------------------------------------
    def call(self, *args: Any, **kwargs: Any) -> Any:
        return self._intentar(lambda: super(GeminiConRespaldo, self).call(*args, **kwargs))

    async def acall(self, *args: Any, **kwargs: Any) -> Any:
        return await self._aintentar(lambda: super(GeminiConRespaldo, self).acall(*args, **kwargs))


def _cadena(primero: str, apoyo: bool = False) -> list[str]:
    """Modelo inicial seguido de la cadena de respaldo, sin duplicados ni prefijo de proveedor. Para los agentes
    de apoyo se prueban antes los modelos lite, para no gastar la cuota de los modelos flash del tutor."""
    respaldo = [_sin_proveedor(m) for m in MODELOS_RESPALDO]
    if apoyo:
        respaldo.sort(key=lambda m: "lite" not in m)
    return list(dict.fromkeys([_sin_proveedor(primero), *respaldo]))


def crear_llm(temperature: float = 0.3, apoyo: bool = False) -> GeminiConRespaldo:
    """LLM del tutor (MODEL) o de los agentes de apoyo (MODEL_APOYO), con la cadena de respaldo detrás."""
    cadena = _cadena(MODEL_APOYO, apoyo=True) if apoyo else _cadena(MODEL)
    # max_tokens incluye los tokens de razonamiento de Gemini; con valores bajos la respuesta se corta.
    return GeminiConRespaldo(model=cadena[0], provider="gemini", cadena=cadena, temperature=temperature,
                             max_tokens=8000, timeout=120)
