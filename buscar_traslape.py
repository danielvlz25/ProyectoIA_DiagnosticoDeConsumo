"""Busca, en el dataset real, cortes cuyas entradas caen en el traslape de las
funciones de pertenencia (dos términos con grado > 0 en exceso y en amplitud).

Uso:  python buscar_traslape.py data/train.parquet
Corre Chronos sobre una muestra de cortes (uno por cada 6 horas) y lista los
mejores candidatos. No usa ningún dato inventado.
"""
import sys

import pandas as pd

from logica_difusa import AMPLITUD, EXCESO, calcular_amplitud, calcular_exceso
from pronostico import PASO, cargar_chronos, cargar_serie, obtener_corte, pronosticar


def main(ruta):
    serie = cargar_serie(ruta)
    pipe = cargar_chronos()
    inicio = serie.index.min() + 15 * pd.Timedelta(days=1)
    candidatos = pd.date_range(inicio, serie.index.max() - PASO, freq="6h")
    encontrados = []
    for ultima in candidatos:
        try:
            corte = obtener_corte(serie, str(ultima))
        except ValueError:
            continue
        if corte.cambio_registrado or not corte.referencia:
            continue
        p10, p50, p90 = pronosticar(corte.contexto, pipe)
        exc = calcular_exceso(p50, corte.referencia)
        amp = calcular_amplitud(p10, p90, corte.referencia)
        ge, ga = EXCESO.fuzzificar(exc), AMPLITUD.fuzzificar(amp)
        n_e = sum(v > 0 for v in ge.values())
        n_a = sum(v > 0 for v in ga.values())
        if n_e == 2 and n_a == 2:
            encontrados.append((str(corte.ultima_lectura), round(p10, 2), round(p50, 2),
                                round(p90, 2), corte.referencia, round(exc, 1), round(amp, 1)))
            print(encontrados[-1])
        if len(encontrados) >= 8:
            break
    print("\nCandidatos (última lectura, P10, P50, P90, referencia, exceso %, amplitud %):")
    for c in encontrados:
        print(c)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python buscar_traslape.py data/train.parquet")
    main(sys.argv[1])