"""Atualização atômica dos snapshots climáticos, compartilhada pelo app e CLI."""
import pandas as pd
from providers import open_meteo
from providers.http import gravar_atomico


def salvar_csv(quadro, arquivo):
    gravar_atomico(arquivo, quadro.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"))



def _ler_existente(arquivo, colunas, datas=False):
    if not arquivo.exists():
        quadro = pd.DataFrame(columns=colunas)
    else:
        quadro = pd.read_csv(arquivo)
    if not set(colunas).issubset(quadro):
        raise ValueError(f"Snapshot inválido: {arquivo}; use --forcar.")
    if datas:
        quadro["data"] = pd.to_datetime(quadro.data)
    return quadro



def baixar_clima(municipios, cfg, forcar=False):
    arquivo = cfg["paths"]["clima_diario"]
    colunas = ["cod_ibge", "data", "chuva_mm", "et0_mm"]
    quadro = _ler_existente(arquivo, colunas, datas=True)
    for m in municipios.itertuples(index=False):
        for ano in cfg["safra"]["anos_disponiveis"]:
            inicio, fim = (pd.Timestamp(f"{ano}-{cfg['safra'][chave]}")
                           for chave in ("inicio_mes_dia", "fim_mes_dia"))
            mascara = quadro.cod_ibge.eq(m.cod_ibge) & quadro.data.between(inicio, fim)
            existente = quadro.loc[mascara].sort_values("data")
            completo = (existente.data.reset_index(drop=True).equals(pd.Series(pd.date_range(inicio, fim)))
                        and not existente.isna().any().any())
            if completo and not forcar:
                print(f"Clima {m.municipio}/{ano}: existente", flush=True)
                continue
            print(f"Baixando clima: {m.municipio}/{ano}", flush=True)
            novo = open_meteo.diario(m.lat, m.lon, inicio, fim, forcar=forcar)
            novo.insert(0, "cod_ibge", int(m.cod_ibge))
            quadro = pd.concat([quadro.loc[~mascara], novo], ignore_index=True)
            salvar_csv(quadro.sort_values(["cod_ibge", "data"]), arquivo)

