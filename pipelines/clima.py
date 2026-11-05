"""Acumulados comparáveis por data de calendário, inclusive anos bissextos."""
import math

import pandas as pd

from providers import dados_locais
from providers.config import carregar


def dias_calendario(datas):
    """1–366 no calendário bissexto de 2000: março nunca desloca entre anos."""
    return pd.Series(datas).map(
        lambda data: pd.Timestamp(data).replace(year=2000).date().timetuple().tm_yday)


def montar_serie(clima, normal, cod_ibge, ano, cfg):
    inicio = pd.Timestamp(f"{ano}-{cfg['safra']['inicio_mes_dia']}")
    fim = pd.Timestamp(f"{ano}-{cfg['safra']['fim_mes_dia']}")
    diario = clima.loc[(clima.cod_ibge == int(cod_ibge)) &
                       clima.data.between(inicio, fim)].sort_values("data").reset_index(drop=True)
    if not diario.data.equals(pd.Series(pd.date_range(inicio, fim))):
        raise ValueError(f"Clima incompleto para {cod_ibge}/{ano}; execute preparar_dados.py.")
    referencia = normal.loc[normal.cod_ibge == int(cod_ibge)].set_index("dia_ano")
    esperado = dias_calendario(diario.data)
    medias = referencia.reindex(esperado)
    valores = diario[["chuva_mm", "et0_mm"]]
    if (medias.isna().any().any() or valores.isna().any().any()
            or not all(math.isfinite(float(v)) and v >= 0 for v in valores.to_numpy().flat)
            or not all(math.isfinite(float(v)) and v >= 0 for v in
                       medias[["chuva_media_mm", "et0_media_mm"]].to_numpy().flat)):
        raise ValueError(f"Clima ou normal inválidos para {cod_ibge}/{ano}.")
    serie = diario[["data"]].copy()
    serie["chuva"] = diario.chuva_mm.to_numpy()
    serie["chuva_acum"] = serie.chuva.cumsum()
    serie["normal_acum"] = medias.chuva_media_mm.to_numpy().cumsum()
    serie["et0"] = diario.et0_mm.to_numpy()
    serie["et0_acum"] = serie.et0.cumsum()
    serie["et0_normal"] = medias.et0_media_mm.to_numpy()
    serie["et0_normal_acum"] = serie.et0_normal.cumsum()
    return serie


def serie_safra(cod_ibge, ano):
    return montar_serie(dados_locais.clima_diario(), dados_locais.climatologia(),
                        cod_ibge, ano, carregar())


def maior_sequencia_seca(serie, limiar_mm):
    """Maior sequência de dias com chuva estritamente menor que o limiar.

    Aceita a coluna chuva (ou chuva_mm), ou uma sequência numérica. NaN não é
    tratado como dia seco: dados faltantes devem ser corrigidos na origem.
    """
    if isinstance(serie, pd.DataFrame):
        serie = serie["chuva" if "chuva" in serie else "chuva_mm"]
    valores = pd.Series(serie, dtype=float)
    if (not math.isfinite(limiar_mm) or limiar_mm < 0
            or not all(math.isfinite(v) and v >= 0 for v in valores)):
        raise ValueError("Chuva e limiar devem ser não negativos e sem lacunas.")
    maior = atual = 0
    for seco in valores.lt(limiar_mm):
        atual = atual + 1 if seco else 0
        maior = max(maior, atual)
    return maior


if __name__ == "__main__":
    cfg = carregar()
    codigo = dados_locais.municipios().iloc[0].cod_ibge
    try:
        print(serie_safra(codigo, cfg["safra"]["ano_padrao"]).tail().to_string(index=False))
    except (FileNotFoundError, ValueError) as erro:
        print(f"Dados indisponíveis: {erro}")
