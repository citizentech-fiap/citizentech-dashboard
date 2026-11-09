"""Orquestração com cache; regras de negócio continuam nos pipelines puros."""
from copy import deepcopy
from threading import RLock

import pandas as pd
import streamlit as st

from pipelines import clima, decisoes, demanda, recomendacoes, risco, realidade
from providers import dados_locais, genai, rpa
from providers.config import carregar
from providers.atualizacao_clima import baixar_clima
from state import store

CFG = carregar()
TTL = CFG["interface"]


def versao_snapshots():
    """Inclui arquivo ausente e alteração externa nas chaves de cache."""
    chaves = ("municipios", "malhas", "clima_diario", "climatologia", "pedidos_snapshot", "rpa_controle", "pam", "garantia_safra", "garantia_safra_cobertura")
    return tuple((str(CFG["paths"][k]), CFG["paths"][k].stat().st_mtime_ns
                  if CFG["paths"][k].exists() else None) for k in chaves)


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def catalogos(versao):
    municipios = dados_locais.municipios()
    try:
        malhas, aviso = dados_locais.malhas(), None
    except (OSError, ValueError):
        malhas, aviso = None, "Mapa indisponível. Consulte a lista de municípios e recupere o snapshot IBGE."
    return municipios, malhas, aviso


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def indicadores(ano, cultura, corte, versao):
    return risco.indicadores(ano, cultura, corte)


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def serie(codigo, ano, versao):
    return clima.serie_safra(codigo, ano)


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def evolucao(ano, cultura, versao):
    return risco.evolucao(ano, cultura, passo="mes")


@st.cache_data(ttl=TTL["cache_rede_ttl_s"], show_spinner=False)
def pedidos(versao):
    try:
        return rpa.pedidos(), None
    except (OSError, ValueError, ImportError):
        if CFG["fontes"]["pedidos"] == "rpa":
            try:
                return rpa.pedidos("snapshot"), "Planilha do robô indisponível. Usando pedidos sintéticos do snapshot."
            except (OSError, ValueError):
                pass
        return pd.DataFrame(columns=[*rpa.COLUNAS, "ano"]), "Pedidos indisponíveis; indicadores climáticos preservados. Recupere o snapshot de pedidos."


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def contexto(ano, cultura, ufs, servico, limiar, versao, corte=None):
    ind = indicadores(ano, cultura, corte, versao)
    ind = ind.loc[ind.uf.isin(ufs)].copy()
    todos, aviso = pedidos(versao)
    if CFG["fontes"]["pedidos"] == "rpa" and not todos.empty and ano not in todos.ano.unique():
        aviso = (aviso + " " if aviso else "") + f"Não há pedidos na fonte para a safra {ano}. Demanda sem dados neste ano; os zeros não indicam ausência de necessidade."
    sel = todos.loc[todos.ano.eq(ano) & todos.uf.isin(ufs)].copy()
    if servico != "todos":
        sel = sel.loc[sel.service_id.eq(servico)]
    dem = demanda.resumo(sel)
    quadro = ind.merge(dem.drop(columns=["municipio", "uf"]), on="cod_ibge", how="left")
    for coluna in ("pedidos", "familias_garantia_safra", "travados_sem_caf", "docs_completos", "revisao_humana"):
        quadro[coluna] = quadro[coluna].fillna(0).astype(int)
    # Limiar exploratório altera a seleção para ação, não a classificação calibrada.
    # O pipeline mantém o critério oficial e as regras administrativas de CAF.
    recs = recomendacoes.gerar(ind, dem, CFG, ano)
    recs = [r for r in recs if r.tipo == "mutirao_caf" or not r.evidencias.get("estimavel", True)
            or r.evidencias["perda_estimada_pct"] >= limiar]
    return {"quadro": quadro, "pedidos": sel, "demanda": dem, "recomendacoes": recs, "aviso": aviso}


def atualizar_municipio(codigo, ano, solicitacao):
    """Reutiliza a gravação atômica e a chamada ao provider da preparação A."""
    chave = (codigo, ano, solicitacao)
    if not store.iniciar_atualizacao(chave):
        return False
    cfg = deepcopy(CFG)
    cfg["safra"]["anos_disponiveis"] = [ano]
    municipios = dados_locais.municipios()
    try:
        baixar_clima(municipios.loc[municipios.cod_ibge.eq(codigo)], cfg, forcar=True)
    finally:
        store.finalizar_atualizacao(chave)
        for cache in (indicadores, serie, evolucao, contexto, validacao):
            cache.clear()
    return True


@st.cache_resource(ttl=TTL["cache_rag_ttl_s"], show_spinner=False)
def recurso_rag():
    rag, motivo = genai.criar_rag()
    # O recurso compartilhado guarda diagnóstico mutável: serializa seu uso.
    return rag, motivo, RLock()


def rascunhar(rec):
    rag, motivo, trava = recurso_rag()
    with trava:
        texto = decisoes.rascunho_convocacao(rec, rag)
    return texto, motivo


def historico():
    # Log pequeno e mutável: leitura sem cache evita ocultar a decisão recém-gravada.
    return decisoes.listar()


def salvar_decisao(rec, escolha, justificativa, mensagem, usuario):
    return decisoes.salvar_decisao(rec, escolha, justificativa, mensagem, usuario, CFG)


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def perda_real(cultura, versao):
    return realidade.perda_real(cultura)


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def pagamentos(versao):
    return realidade.pagamentos()


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def validacao(cultura, versao):
    return realidade.validacao(cultura)


@st.cache_data(ttl=TTL["cache_dados_ttl_s"], show_spinner=False)
def cobertura_pagamentos(ano, versao):
    return realidade._cobertura_pagamentos(ano, CFG)


@st.cache_data(ttl=TTL["cache_rag_ttl_s"], show_spinner=False)
def gerar_texto(sistema, payload):
    return genai.gerar_texto(sistema, payload)
