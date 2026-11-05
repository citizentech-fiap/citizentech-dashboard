"""Malhas municipais simplificadas do IBGE."""
import json

from providers import http


def malha(cod_ibge, *, forcar=False) -> dict:
    url = f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{int(cod_ibge)}"
    dados = json.loads(http.get(url, {"formato": "application/vnd.geo+json",
                                      "qualidade": "minima"}, forcar=forcar))
    if dados.get("type") != "FeatureCollection" or not dados.get("features"):
        raise ValueError(f"Malha inválida para o município {cod_ibge}.")
    return dados
