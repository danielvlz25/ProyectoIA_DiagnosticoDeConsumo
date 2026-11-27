"""Carga de datos, validación de cortes, referencia y pronóstico con Chronos."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

import pandas as pd

PASO = pd.Timedelta(minutes=10)
LECTURAS_CONTEXTO = 144
DIAS_PREVIOS = 14

# Cortes de la tarea (sección 6.1): última lectura disponible y lectura a pronosticar
CORTES_HISTORICOS = {
    "H1 · Mañana": ("2016-02-15 06:50", "2016-02-15 07:00"),
    "H2 · Mediodía": ("2016-03-15 13:50", "2016-03-15 14:00"),
    "H3 · Tarde": ("2016-04-15 18:40", "2016-04-15 18:50"),
}


def cargar_serie(ruta: str) -> pd.Series:
    """Devuelve Appliances indexada por fecha, ordenada cronológicamente."""
    df = pd.read_parquet(ruta, columns=["date", "Appliances"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")["Appliances"]


@dataclass
class Corte:
    ultima_lectura: pd.Timestamp
    objetivo: pd.Timestamp
    contexto: pd.Series
    continuo: bool
    previos: list[float]
    dias_previos_completos: bool
    referencia: float | None
    cambio_registrado: str = ""


def _evaluar_corte(serie: pd.Series, ultima: pd.Timestamp) -> Corte:
    objetivo = ultima + PASO
    contexto = serie.loc[ultima - (LECTURAS_CONTEXTO - 1) * PASO: ultima]
    continuo = (len(contexto) == LECTURAS_CONTEXTO and
                bool((contexto.index.to_series().diff().dropna() == PASO).all()))
    previos = []
    for k in range(1, DIAS_PREVIOS + 1):
        v = serie.get(objetivo - pd.Timedelta(days=k))
        if v is not None and not pd.isna(v):
            previos.append(float(v))
    referencia = float(median(previos)) if previos else None
    return Corte(ultima, objetivo, contexto, continuo, previos,
                 len(previos) == DIAS_PREVIOS, referencia)


def obtener_corte(serie: pd.Series, ultima_lectura: str) -> Corte:
    """Valida el corte; si no cumple, toma el siguiente corte válido y lo registra."""
    ultima = pd.Timestamp(ultima_lectura)
    original = ultima
    limite = serie.index.max() - PASO
    while ultima <= limite:
        corte = _evaluar_corte(serie, ultima)
        if corte.continuo and corte.dias_previos_completos and corte.objetivo in serie.index:
            if ultima != original:
                corte.cambio_registrado = (
                    f"El corte {original} no cumplía las condiciones; se usó {ultima}.")
            return corte
        ultima += PASO
    raise ValueError("No se encontró un corte válido.")


_pipeline = None


def cargar_chronos():
    """Carga Chronos-Bolt Tiny (se descarga la primera vez)."""
    global _pipeline
    if _pipeline is None:
        from chronos import BaseChronosPipeline
        _pipeline = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-tiny")
    return _pipeline


def pronosticar(contexto: pd.Series, pipeline=None) -> tuple[float, float, float]:
    """Devuelve (P10, P50, P90) del siguiente intervalo de 10 minutos."""
    import torch
    pipeline = pipeline or cargar_chronos()
    cuantiles, _ = pipeline.predict_quantiles(
        torch.tensor(contexto.values, dtype=torch.float32),
        prediction_length=1, quantile_levels=[0.1, 0.5, 0.9])
    p10, p50, p90 = (float(x) for x in cuantiles[0, 0])
    return p10, p50, p90