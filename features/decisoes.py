"""Fila de ações humanas e histórico de auditoria recolhido."""
import pandas as pd
import streamlit as st

from pipelines.decisoes import selos
from pipelines.recomendacoes import ROTULOS_TIPOS
from state import dados, store
from ui.acoes import Servicos
from ui.componentes import cartao_recomendacao
from ui.graficos import barras_contagens


def fila_pendente(ctx, codigo=None):
    try:
        historico = dados.historico()
    except (OSError, ValueError):
        st.error("Não foi possível ler a auditoria. Recupere o histórico antes de registrar novas decisões.")
        return None, []
    decididas = {r["id"] for r in historico}
    fila = [r for r in ctx["recomendacoes"] if r.id not in decididas
            and (codigo is None or r.cod_ibge == codigo)]
    return fila, historico


def acoes_municipio(ctx, cfg, filtros, codigo, nome):
    st.subheader(f"O que fazer em {nome}")
    fila, historico = fila_pendente(ctx, codigo)
    if fila is None:
        return
    if not fila:
        st.success("Nenhuma ação aguardando decisão neste município.")
    aviso_gestor(fila)
    for rec in fila:
        cartao(rec, cfg, filtros)
    decididas(ctx, cfg, filtros, historico, codigo)


def renderizar(ctx, cfg, filtros):
    fila, historico = fila_pendente(ctx)
    if fila is None:
        return
    st.subheader(f"{len(fila)} ações aguardando sua decisão — comece pelas mais urgentes.")
    oficial = cfg["risco"]["criterio_garantia_safra"]
    if not ctx["quadro"].perda_estimada_pct.ge(oficial).any():
        st.success(f"Nenhum município atingiu o critério de {oficial}% nesta safra. Nenhuma vistoria necessária.")
        st.caption("Pendências de CAF ainda podem precisar de atendimento.")
    if not fila:
        st.success("Tudo em dia: nenhuma ação aguardando sua decisão.")
    aviso_gestor(fila)
    for rec in fila[:store.obter("acoes_visiveis")]:
        cartao(rec, cfg, filtros)
    if len(fila) > store.obter("acoes_visiveis"):
        tamanho = cfg["interface"]["recomendacoes_por_pagina"]
        st.button(f"Mostrar mais {tamanho}", key="mostrar_mais", on_click=store.mostrar_mais, args=(tamanho,))
    with st.expander("Decisões já tomadas"):
        municipios = set(ctx["quadro"].municipio)
        registros = [r for r in historico if r["id"].endswith(f"-{filtros['ano']}") and r["municipio"] in municipios]
        st.caption("Histórico da safra e dos estados selecionados, incluindo ações que já saíram da fila.")
        decididas(ctx, cfg, filtros, historico)
        if registros:
            contagens = pd.DataFrame(registros).groupby("decisao").size().reset_index(name="quantidade").rename(columns={"decisao": "categoria"})
            st.plotly_chart(barras_contagens(contagens, cfg["interface"]["altura_barras"]), key="grafico_decisoes")
            tabela = pd.DataFrame(registros).iloc[::-1]
            st.dataframe(_tabela_legivel(tabela), hide_index=True, width="stretch")
            st.download_button("Baixar histórico (CSV)", tabela.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"decisoes-{filtros['ano']}.csv", mime="text/csv")
        else:
            st.caption("Suas decisões aparecerão aqui.")


def _tabela_legivel(tabela):
    """Histórico para leitura humana: hora local, nomes em vez de códigos. O CSV baixado mantém os dados brutos."""
    from pipelines.recomendacoes import ROTULOS_TIPOS
    quando = pd.to_datetime(tabela["quando"], utc=True, errors="coerce").dt.tz_convert("America/Recife")
    return pd.DataFrame({
        "Quando": quando.dt.strftime("%d/%m %H:%M"),
        "Município": tabela["municipio"],
        "Ação": tabela["tipo"].map(lambda t: ROTULOS_TIPOS.get(t, t)),
        "Decisão": tabela["decisao"].str.capitalize(),
        "Por quem": tabela["usuario"],
        "Motivo / justificativa": tabela["justificativa"].fillna("").str.split("\n").str[0],
    })


def cartao(rec, cfg, filtros, decisao=None):
    servicos = Servicos(salvar=dados.salvar_decisao, rascunhar=dados.rascunhar)
    cartao_recomendacao(rec, cfg, filtros, ROTULOS_TIPOS[rec.tipo], servicos, decisao)


def decididas(ctx, cfg, filtros, historico, codigo=None):
    registros = selos(historico)
    for rec in ctx["recomendacoes"]:
        if rec.id in registros and (codigo is None or rec.cod_ibge == codigo):
            cartao(rec, cfg, filtros, registros[rec.id])


def aviso_gestor(fila):
    if fila and not store.obter("gestor", "").strip():
        st.info("Para aprovar, ajustar ou recusar, preencha a identificação funcional do gestor na barra lateral.")
