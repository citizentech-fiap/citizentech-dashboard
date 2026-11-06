"""Produção Agrícola Municipal, SIDRA 1612.

Convenção do IBGE: "-" é zero absoluto (ex.: safra perdida em 2012) e vira 0;
"..", "..." (não se aplica / não disponível) e "X" (sigilo) viram NaN, nunca zero.
"""
import json

import pandas as pd

from providers import http

VARIAVEIS = {"109": "area_plantada_ha", "216": "area_colhida_ha", "214": "producao_t"}
CULTURAS = {"2711": "milho", "2702": "feijao"}
COLUNAS = ["cod_ibge", "ano", "cultura", *VARIAVEIS.values()]


def parsear(bruto):
    """Dimensões seguem a ordem explícita n6/v/p/c81 da consulta."""
    dados = json.loads(bruto) if isinstance(bruto, (bytes, str)) else bruto
    if not isinstance(dados, list) or len(dados) < 2:
        raise ValueError("Resposta PAM vazia ou inválida.")
    linhas = []
    for item in dados[1:]:
        try:
            valor = item["V"]
            valor = 0.0 if valor == "-" else (float("nan") if valor in ("..", "...", "X") else float(valor))
            if not pd.isna(valor) and (valor < 0 or valor == float("inf")):
                raise ValueError("Medida PAM inválida.")
            linhas.append({"cod_ibge": int(item["D1C"]), "ano": int(item["D3C"]),
                           "cultura": CULTURAS[item["D4C"]],
                           "variavel": VARIAVEIS[item["D2C"]],
                           "valor": valor})
        except (KeyError, TypeError, ValueError) as erro:
            raise ValueError("Dimensões inesperadas na resposta PAM.") from erro
    quadro = pd.DataFrame(linhas)
    if quadro.duplicated(["cod_ibge", "ano", "cultura", "variavel"]).any():
        raise ValueError("Resposta PAM com observações duplicadas.")
    if not quadro.groupby(["cod_ibge", "ano", "cultura"]).variavel.nunique().eq(len(VARIAVEIS)).all():
        raise ValueError("Resposta PAM com variáveis ausentes.")
    return (quadro.pivot(index=["cod_ibge", "ano", "cultura"], columns="variavel", values="valor")
            .reindex(columns=VARIAVEIS.values()).reset_index().rename_axis(columns=None)[COLUNAS])


def producao(codigos, anos, *, forcar=False):
    codigos, anos = sorted(set(map(int, codigos))), sorted(set(map(int, anos)))
    if not codigos or not anos:
        return pd.DataFrame(columns=COLUNAS)
    url = ("https://apisidra.ibge.gov.br/values/t/1612/n6/" + ",".join(map(str, codigos))
           + "/v/109,216,214/p/" + ",".join(map(str, anos)) + "/c81/2711,2702?formato=json")
    quadro = parsear(http.get(url, forcar=forcar))
    esperado = pd.MultiIndex.from_product([codigos, anos, CULTURAS.values()],
                                         names=["cod_ibge", "ano", "cultura"])
    if set(map(tuple, quadro[["cod_ibge", "ano", "cultura"]].to_numpy())) != set(esperado):
        raise ValueError("Resposta PAM incompleta para municípios/anos solicitados.")
    return quadro
