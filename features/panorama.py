"""Panorama: localizar o problema e escolher onde investigar primeiro."""
import pandas as pd
import streamlit as st

from state import dados, store
from ui.componentes import abrir_raio_x, badge_risco, kpi
from ui.graficos import MESES, grafico_chuva, mapa_perdas


def renderizar(ctx, cfg, filtros, versao, malhas):
    st.subheader("Onde agir primeiro?")
    st.caption("Compare a perda estimada, confira a chuva e abra as evidências antes de decidir.")
    inicio, fim = (int(cfg["safra"][chave][:2]) for chave in ("inicio_mes_dia", "fim_mes_dia"))
    st.slider("Replay da safra · mês", inicio, fim, key="mes", format="Mês %d")
    mes = store.obter("mes")
    corte = min(pd.Timestamp(f"{filtros['ano']}-{mes:02d}-01") + pd.offsets.MonthEnd(0),
                pd.Timestamp(f"{filtros['ano']}-{cfg['safra']['fim_mes_dia']}"))
    with st.spinner("Recalculando o panorama até o mês escolhido…"):
        replay = dados.contexto(**filtros, versao=versao, corte=corte.date().isoformat())
    quadro = replay["quadro"].sort_values("perda_estimada_pct", ascending=False)
    alerta = quadro.perda_estimada_pct.ge(filtros["limiar"])
    st.caption(f"LEITURA ATÉ {corte:%d/%m/%Y} · clima até {MESES[mes-1].lower()} · pedidos sintéticos da safra inteira")
    a, b, c = st.columns(3)
    with a:
        kpi("Municípios no limiar", f"{alerta.sum()} de {len(quadro)}", f"Perda estimada ≥ {filtros['limiar']}%", "alerta" if alerta.any() else "seguro")
    with b:
        kpi("Maior perda estimada", f"{quadro.perda_estimada_pct.max():.0f}%", quadro.iloc[0].municipio, quadro.iloc[0].classe)
    with c:
        kpi("Pedidos no recorte", f"{quadro.pedidos.sum():,}".replace(",", "."), "Famílias fictícias · base sintética")
    mapa, lista = st.columns([2.1, 1])
    with mapa:
        st.markdown("### Territórios sob pressão")
        st.caption("Passe o cursor sobre o município · arraste ou amplie o mapa")
        if malhas:
            st.plotly_chart(mapa_perdas(quadro, malhas, cfg, cfg["interface"]["altura_mapa"]),
                            key="mapa_perdas", config={"displayModeBar": False},
                            alt="Polígonos IBGE por perda estimada. A lista ao lado traz os valores e as classes em texto.")
        else:
            st.info("Consulte os valores municipais na lista ao lado; o snapshot de malhas está indisponível.")
    with lista:
        st.markdown("### Comece por aqui")
        st.caption("Maiores perdas estimadas no mês selecionado")
        for indice, linha in enumerate(quadro.head(cfg["interface"]["mini_graficos"]).itertuples()):
            with st.container(border=True):
                st.markdown(f"**{indice+1:02d} · {linha.municipio} / {linha.uf}**")
                badge_risco(linha.classe)
                st.write(f"**{linha.perda_estimada_pct:.0f}%** de perda · {linha.pedidos} pedidos")
                abrir_raio_x(linha.cod_ibge, f"panorama_abrir_{linha.cod_ibge}", "Investigar município →")
    st.markdown("### Como a safra chegou até aqui")
    st.caption("Chuva acumulada e normal (mm) · faixa cinza: necessidade de água da cultura (ETc, ano/normal) · perda no eixo direito (%)")
    evolucao = dados.evolucao(filtros["ano"], filtros["cultura"], versao)
    for coluna, linha in zip(st.columns(cfg["interface"]["mini_graficos"]), quadro.head(cfg["interface"]["mini_graficos"]).itertuples()):
        with coluna:
            st.markdown(f"**{linha.municipio}**")
            serie = dados.serie(int(linha.cod_ibge), filtros["ano"], versao)
            serie = serie.loc[serie.data.le(corte)]
            ev = evolucao.loc[evolucao.cod_ibge.eq(linha.cod_ibge) & evolucao.data.le(corte)]
            st.plotly_chart(grafico_chuva(serie, cfg["interface"]["altura_mini"], compacto=True,
                cfg=cfg, cultura=filtros["cultura"], limiar=filtros["limiar"], evolucao=ev),
                key=f"mini_{linha.cod_ibge}", config={"displayModeBar": False})
    with st.expander("Todos os municípios · valores do replay"):
        st.dataframe(quadro[["municipio", "uf", "perda_estimada_pct", "classe", "chuva_mm", "normal_mm", "pedidos"]],
                     hide_index=True, width="stretch")
