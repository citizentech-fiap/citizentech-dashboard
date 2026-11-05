"""Pedidos sem dados pessoais: snapshot sintético ou planilha viva do robô."""
import pandas as pd

from providers.config import carregar

COLUNAS = ["request_id", "data_envio", "municipio", "uf", "cod_ibge", "service_id",
           "confianca", "decisao", "motivo", "docs_presentes", "docs_faltantes",
           "docs_ilegiveis", "fonte_resposta"]


def pedidos(fonte=None):
    cfg = carregar()
    fonte = fonte or cfg["fontes"]["pedidos"]
    if fonte not in ("snapshot", "rpa"):
        raise ValueError("Fonte de pedidos deve ser 'snapshot' ou 'rpa'.")
    arquivo = cfg["paths"]["pedidos_snapshot" if fonte == "snapshot" else "rpa_controle"]
    if not arquivo.is_file():
        raise FileNotFoundError(f"Fonte '{fonte}' de pedidos ausente: {arquivo}")
    if fonte == "snapshot":
        dados = pd.read_csv(arquivo, keep_default_na=False)
    else:
        dados = pd.read_excel(arquivo, sheet_name="solicitacoes", keep_default_na=False)
    faltantes = set(COLUNAS) - set(dados.columns)
    if faltantes:
        raise ValueError(f"Pedidos sem colunas obrigatórias: {sorted(faltantes)}")
    # Seleção explícita impede expor nomes ou outros campos pessoais da planilha.
    anos = pd.to_datetime(dados["data_envio"], errors="raise", utc=True).dt.year
    if "ano" in dados and not pd.to_numeric(dados["ano"]).eq(anos).all():
        raise ValueError("Ano do pedido diverge de data_envio.")
    saida = dados[COLUNAS].copy()
    saida["ano"] = anos
    saida["cod_ibge"] = pd.to_numeric(saida["cod_ibge"], errors="coerce").astype("Int64")
    return saida
