"""Leitura e validação mínima dos snapshots; erros podem virar avisos na UI."""
import json

import pandas as pd

from providers.config import carregar


def caminho(chave):
    arquivo = carregar()["paths"][chave]
    if not arquivo.is_file():
        raise FileNotFoundError(
            f"Snapshot '{chave}' ausente: {arquivo}. Execute scripts/preparar_dados.py."
        )
    return arquivo


def _csv(chave, colunas):
    quadro = pd.read_csv(caminho(chave), encoding="utf-8", dtype={"cod_ibge": "int64"})
    ausentes = set(colunas) - set(quadro.columns)
    if ausentes:
        raise ValueError(f"Snapshot '{chave}' sem colunas: {sorted(ausentes)}")
    if quadro[list(colunas)].isna().any().any():
        raise ValueError(f"Snapshot '{chave}' contém valores ausentes.")
    return quadro


def municipios():
    return _csv("municipios", ["municipio", "uf", "cod_ibge", "lat", "lon"])


def malhas():
    dados = json.loads(caminho("malhas").read_text(encoding="utf-8"))
    if dados.get("type") != "FeatureCollection" or not dados.get("features"):
        raise ValueError("Snapshot de malhas inválido.")
    return dados


def clima_diario():
    quadro = _csv("clima_diario", ["cod_ibge", "data", "chuva_mm", "et0_mm"])
    quadro["data"] = pd.to_datetime(quadro["data"], errors="raise")
    if quadro.duplicated(["cod_ibge", "data"]).any():
        raise ValueError("Clima diário contém datas duplicadas por município.")
    return quadro


def climatologia():
    quadro = _csv("climatologia", ["cod_ibge", "dia_ano", "chuva_media_mm", "et0_media_mm"])
    if quadro.duplicated(["cod_ibge", "dia_ano"]).any():
        raise ValueError("Climatologia contém dias duplicados por município.")
    return quadro


def pam():
    from providers.ibge_pam import COLUNAS
    quadro = pd.read_csv(caminho("pam"), encoding="utf-8")
    if not set(COLUNAS).issubset(quadro) or quadro.duplicated(["cod_ibge", "ano", "cultura"]).any():
        raise ValueError("Snapshot PAM inválido.")
    # NaN nas medidas é parte do contrato SIDRA, não erro de leitura.
    if quadro[["cod_ibge", "ano", "cultura"]].isna().any().any():
        raise ValueError("Snapshot PAM sem identificação municipal/ano/cultura.")
    return quadro[COLUNAS]


def garantia_safra():
    from providers.transparencia import COLUNAS
    quadro = _csv("garantia_safra", COLUNAS)
    if quadro.duplicated(["cod_ibge", "safra"]).any():
        raise ValueError("Pagamentos duplicados por município/safra.")
    return quadro[COLUNAS]
