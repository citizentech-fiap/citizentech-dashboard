"""Primeiro passo: localizar as maiores perdas e abrir um município."""
import pandas as pd
import streamlit as st

from state import dados, store
from ui.componentes import abrir_raio_x, badge_risco, como_calculamos, kpi
from ui.graficos import MESES, grafico_chuva, mapa_perdas


def renderizar(ctx, cfg, filtros, versao, malhas):
    inicio, fim = (int(cfg["safra"][chave][:2]) for chave in ("inicio_mes_dia", "fim_mes_dia"))
    mes = store.obter("mes")
    corte = min(pd.Timestamp(f"{filtros['ano']}-{mes:02d}-01") + pd.offsets.MonthEnd(0),
                pd.Timestamp(f"{filtros['ano']}-{cfg['safra']['fim_mes_dia']}"))
    with st.spinner("Preparando o mapa até o mês escolhido…"):
        replay = dados.contexto(**filtros, versao=versao, corte=corte.date().isoformat())
    quadro = replay["quadro"].sort_values(["perda_estimada_pct", "cod_ibge"], ascending=[False, True])
    oficial = cfg["risco"]["criterio_garantia_safra"]
    alerta = quadro.perda_estimada_pct.ge(oficial)
    a, b, c = st.columns(3)
    with a:
        kpi(f"Municípios com perda ≥ {oficial}%", f"{alerta.sum()} de {len(quadro)}", cor="alerta" if alerta.any() else "seguro")
    with b:
        kpi("Maior perda", f"{quadro.perda_estimada_pct.max():.0f}%", quadro.iloc[0].municipio, quadro.iloc[0].classe)
    with c:
        kpi("Pedidos de agricultores", f"{quadro.pedidos.sum():,}".replace(",", "."), "Sintéticos · sem dados pessoais")
    mapa, lista = st.columns([2.1, 1])
    with mapa:
        st.slider("Reveja a safra mês a mês", inicio, fim, key="mes", format="Mês %d")
        st.caption(f"Até {corte:%d/%m/%Y} · {MESES[mes-1]} · pedidos sintéticos da safra inteira")
        if malhas:
            st.plotly_chart(mapa_perdas(quadro, malhas, cfg, cfg["interface"]["altura_mapa"]),
                            key="mapa_perdas", config={"displayModeBar": False},
                            alt="Municípios por perda estimada. A lista ao lado traz os valores e as classes.")
        else:
            st.info("Mapa indisponível. Consulte os municípios na lista ao lado.")
    with lista:
        st.markdown("### Comece por aqui")
        for indice, linha in enumerate(quadro.head(cfg["interface"]["mini_graficos"]).itertuples()):
            with st.container(border=True):
                st.markdown(f"**{indice+1} · {linha.municipio} / {linha.uf}**")
                badge_risco(linha.classe)
                chuva = (f"chuva {abs(linha.anomalia_pct):.0f}% {'abaixo' if linha.anomalia_pct < 0 else 'acima'} do normal"
                         if pd.notna(linha.anomalia_pct) else "comparação de chuva indisponível")
                st.write(f"Perda estimada {linha.perda_estimada_pct:.0f}% · {chuva} · {linha.pedidos} pedidos")
                serie = dados.serie(int(linha.cod_ibge), filtros["ano"], versao)
                st.plotly_chart(grafico_chuva(serie.loc[serie.data.le(corte)], cfg["interface"]["altura_mini"],
                                compacto=True, cfg=cfg, cultura=filtros["cultura"], limiar=filtros["limiar"]),
                                key=f"mini_{linha.cod_ibge}", config={"displayModeBar": False})
                abrir_raio_x(linha.cod_ibge, f"panorama_abrir_{linha.cod_ibge}", "Ver por quê →")
    with st.expander("Todos os municípios · mês selecionado"):
        st.dataframe(quadro[["municipio", "uf", "perda_estimada_pct", "classe", "chuva_mm", "normal_mm", "pedidos"]].rename(
            columns={"municipio": "Município", "uf": "UF", "perda_estimada_pct": "Perda estimada (%)",
                     "classe": "Risco", "chuva_mm": "Chuva (mm)", "normal_mm": "Normal (mm)", "pedidos": "Pedidos"}),
                     hide_index=True, width="stretch")
    como_calculamos(cfg, filtros)
