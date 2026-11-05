"""Fila de ações humanas e histórico de auditoria recolhido."""
import pandas as pd
import streamlit as st

from state import dados, store
from ui.componentes import cartao_recomendacao


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
    fila, _ = fila_pendente(ctx, codigo)
    if fila is None:
        return
    if not fila:
        st.success("Nenhuma ação aguardando decisão neste município.")
    for rec in fila:
        cartao_recomendacao(rec, cfg, filtros)


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
    for rec in fila[:store.obter("acoes_visiveis")]:
        cartao_recomendacao(rec, cfg, filtros)
    if len(fila) > store.obter("acoes_visiveis"):
        tamanho = cfg["interface"]["recomendacoes_por_pagina"]
        st.button(f"Mostrar mais {tamanho}", key="mostrar_mais", on_click=store.mostrar_mais, args=(tamanho,))
    with st.expander("Decisões já tomadas"):
        municipios = set(ctx["quadro"].municipio)
        registros = [r for r in historico if r["id"].endswith(f"-{filtros['ano']}") and r["municipio"] in municipios]
        st.caption("Histórico da safra e dos estados selecionados, incluindo ações que já saíram da fila.")
        if registros:
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
