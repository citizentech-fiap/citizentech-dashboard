"""Indicadores municipais e replay; sem inferir aprovação do benefício."""
import argparse

import pandas as pd

from pipelines.clima import montar_serie, maior_sequencia_seca
from pipelines.modelo_hidrico import calcular
from providers import dados_locais
from providers.config import carregar

COLUNAS = ["cod_ibge", "municipio", "uf", "chuva_mm", "normal_mm", "anomalia_pct",
           "maior_seca_dias", "deficit_hidrico_mm", "isna_ano", "isna_normal",
           "razao_isna", "perda_estimada_pct", "classe"]


def classificar(perda, cfg):
    if pd.isna(perda) or not 0 <= perda <= 100:
        raise ValueError("Perda deve estar entre 0 e 100%.")
    classes = cfg.get("risco", cfg)["classes"]
    return max((nome for nome, minimo in classes.items() if perda >= minimo),
               key=classes.get)


def _indicadores(series, municipios, cultura, corte, cfg):
    linhas = []
    for municipio in municipios.itertuples(index=False):
        serie = series[municipio.cod_ibge]
        periodo = serie.loc[serie.data <= corte]
        chuva = float(periodo.chuva.sum())
        normal = float(periodo.normal_acum.iloc[-1]) if len(periodo) else 0.0
        modelo = calcular(chuva, periodo.et0.sum(), cultura, cfg,
                          chuva_normal_mm=normal, et0_normal_mm=periodo.et0_normal.sum())
        linhas.append({"cod_ibge": municipio.cod_ibge, "municipio": municipio.municipio,
                       "uf": municipio.uf, "chuva_mm": chuva, "normal_mm": normal,
                       "anomalia_pct": (chuva / normal - 1) * 100 if normal else float("nan"),
                       "maior_seca_dias": maior_sequencia_seca(
                           periodo, cfg["modelo_hidrico"]["dia_seco_mm"]),
                       **modelo, "classe": classificar(modelo["perda_estimada_pct"], cfg)})
    return pd.DataFrame(linhas, columns=COLUNAS)


def _carregar(ano, cfg):
    municipios = dados_locais.municipios()
    clima, normal = dados_locais.clima_diario(), dados_locais.climatologia()
    series = {int(cod): montar_serie(clima, normal, cod, ano, cfg)
              for cod in municipios.cod_ibge}
    return municipios, series


def indicadores(ano, cultura, ate_data=None):
    cfg = carregar()
    inicio = pd.Timestamp(f"{ano}-{cfg['safra']['inicio_mes_dia']}")
    fim = pd.Timestamp(f"{ano}-{cfg['safra']['fim_mes_dia']}")
    corte = pd.Timestamp(ate_data) if ate_data is not None else fim
    if corte < inicio or corte > fim:
        raise ValueError(f"Data de corte deve pertencer à safra {inicio.date()}–{fim.date()}.")
    municipios, series = _carregar(ano, cfg)
    return _indicadores(series, municipios, cultura, corte, cfg)


def evolucao(ano, cultura, passo="semana"):
    cfg = carregar()
    frequencias = {"dia": "D", "semana": "7D", "mes": "ME"}
    if passo not in frequencias:
        raise ValueError("Passo deve ser dia, semana ou mes.")
    inicio = pd.Timestamp(f"{ano}-{cfg['safra']['inicio_mes_dia']}")
    fim = pd.Timestamp(f"{ano}-{cfg['safra']['fim_mes_dia']}")
    cortes = pd.date_range(inicio, fim, freq=frequencias[passo]).union(pd.DatetimeIndex([fim]))
    municipios, series = _carregar(ano, cfg)
    return pd.concat([_indicadores(series, municipios, cultura, corte, cfg).assign(data=corte)
                      for corte in cortes], ignore_index=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=carregar()["safra"]["ano_padrao"])
    parser.add_argument("--cultura", default=carregar()["modelo_hidrico"]["cultura_padrao"])
    args = parser.parse_args()
    try:
        resultado = indicadores(args.ano, args.cultura)
        print(f"Safra {args.ano} — {args.cultura} — ISNA relativo à normal 1991–2020 (adaptação FAO-33)")
        print(resultado.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
        print("Classes:", resultado.classe.value_counts().to_dict())
    except (FileNotFoundError, ValueError) as erro:
        print(f"Dados indisponíveis: {erro}")
