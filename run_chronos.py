"""Corre Chronos-Bolt Tiny en los cortes H1-H3 y guarda P10/P50/P90 + referencia.

Uso:
    python run_chronos.py train.parquet
Salida: resultados_chronos.json
"""
import json
import sys
from statistics import median

import pandas as pd
import torch
from chronos import BaseChronosPipeline

CORTES = {
    "H1": ("2016-02-15 06:50", "2016-02-15 07:00"),
    "H2": ("2016-03-15 13:50", "2016-03-15 14:00"),
    "H3": ("2016-04-15 18:40", "2016-04-15 18:50"),
}
PASO = pd.Timedelta(minutes=10)


def cargar(ruta):
    df = pd.read_parquet(ruta, columns=["date", "Appliances"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")["Appliances"]


def main(ruta):
    serie = cargar(ruta)
    pipe = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-tiny")
    salida = {}
    for caso, (ultima, objetivo) in CORTES.items():
        ultima, objetivo = pd.Timestamp(ultima), pd.Timestamp(objetivo)
        ctx = serie.loc[ultima - 143 * PASO : ultima]
        continuo = len(ctx) == 144 and (ctx.index.to_series().diff().dropna() == PASO).all()
        previos = [serie.get(objetivo - pd.Timedelta(days=k)) for k in range(1, 15)]
        previos = [float(v) for v in previos if v is not None and not pd.isna(v)]

        cuantiles, _ = pipe.predict_quantiles(
            torch.tensor(ctx.values, dtype=torch.float32),
            prediction_length=1,
            quantile_levels=[0.1, 0.5, 0.9],
        )
        p10, p50, p90 = (float(x) for x in cuantiles[0, 0])
        salida[caso] = {
            "ultima_lectura": str(ultima),
            "objetivo": str(objetivo),
            "lecturas_contexto": len(ctx),
            "contexto_continuo": bool(continuo),
            "dias_previos_disponibles": len(previos),
            "referencia": median(previos) if previos else None,
            "P10": p10,
            "P50": p50,
            "P90": p90,
        }
        print(caso, salida[caso])

    with open("resultados_chronos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    print("\nListo. Se guardó resultados_chronos.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python run_chronos.py ruta/a/train.parquet")
    main(sys.argv[1])