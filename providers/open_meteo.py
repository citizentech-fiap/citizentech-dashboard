"""Séries diárias reais do Open-Meteo Archive (uma chamada por intervalo)."""
import json
import math

import pandas as pd

from providers import http

URL = "https://archive-api.open-meteo.com/v1/archive"
# Série homogênea: o padrão "best_match" troca de modelo a partir de 2017 e infla a chuva
# no semiárido (Quixadá jan–jun/2019: 1.081 mm no best_match × 742 mm no ERA5), o que
# esconderia secas reais quando comparadas à normal 1991–2020 (quase toda ERA5).
MODELO = "era5"


def diario(lat, lon, inicio, fim, *, forcar=False) -> pd.DataFrame:
    inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    if fim < inicio:
        raise ValueError("Fim do intervalo anterior ao início.")
    bruto = json.loads(http.get(URL, {
        "latitude": lat, "longitude": lon,
        "start_date": inicio.strftime("%Y-%m-%d"),
        "end_date": fim.strftime("%Y-%m-%d"),
        "daily": "precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "America/Recife",
        "models": MODELO,
    }, forcar=forcar))
    try:
        dados = bruto["daily"]
        quadro = pd.DataFrame({"data": pd.to_datetime(dados["time"]),
                               "chuva_mm": dados["precipitation_sum"],
                               "et0_mm": dados["et0_fao_evapotranspiration"]})
        for coluna in ("chuva_mm", "et0_mm"):
            quadro[coluna] = pd.to_numeric(quadro[coluna], errors="raise")
        esperado = pd.date_range(inicio, fim)
        if not quadro["data"].equals(pd.Series(esperado)):
            raise ValueError("Datas ausentes, repetidas ou fora de ordem")
        valores = quadro[["chuva_mm", "et0_mm"]]
        if quadro.isna().any().any() or not all(
                math.isfinite(float(valor)) and valor >= 0 for valor in valores.to_numpy().flat):
            raise ValueError("Valores ausentes, infinitos ou negativos")
    except (KeyError, ValueError, TypeError) as erro:
        raise ValueError(f"Resposta climática inválida para {lat}, {lon}: {erro}") from erro
    return quadro
