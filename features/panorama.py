"""Primeiro passo: localizar as maiores perdas e abrir um município."""
import pandas as pd
import streamlit as st

from features.metodo import como_calculamos
from pipelines.risco import classificar
from state import dados, store
from ui.componentes import abrir_raio_x, badge_risco, kpi, percentual, selo_simulado
from ui import tema
from ui.graficos import MESES, grafico_chuva, mapa_perdas


def renderizar(ctx, cfg, filtros, versao, malhas):
    inicio, fim = (int(cfg["safra"][chave][:2]) for chave in ("inicio_mes_dia", "fim_mes_dia"))
    mes = store.obter("mes")
    corte = min(pd.Timestamp(f"{filtros['ano']}-{mes:02d}-01") + pd.offsets.MonthEnd(0),
                pd.Timestamp(f"{filtros['ano']}-{cfg['safra']['fim_mes_dia']}"))
    with st.spinner("Preparando o mapa até o mês escolhido…"):
        replay = dados.contexto(**filtros, versao=versao, corte=corte.date().isoformat())
    quadro = replay["quadro"].sort_values(["perda_estimada_pct", "cod_ibge"], ascending=[False, True])
    estimavel = bool(quadro.estimavel.all())
    if not estimavel:
        quadro = quadro.sort_values(["anomalia_pct", "cod_ibge"])
    try:
        real = dados.perda_real(filtros["cultura"], versao)
        real = real.loc[real.ano.eq(filtros["ano"]), ["cod_ibge", "perda_producao_pct"]]
        quadro = quadro.merge(real, on="cod_ibge", how="left")
    except (OSError, ValueError):
        quadro["perda_producao_pct"] = float("nan")
        st.warning("Produção IBGE indisponível; recupere o arquivo local.")
    try:
        registros = dados.historico()
    except (OSError, ValueError):
        registros = []
        st.warning("Histórico indisponível; ações aprovadas não puderam ser marcadas.")
    # id das recomendações: "<tipo>-<cod_ibge>-<safra>" (pipelines/recomendacoes.py)
    aprovados = {int(r["id"].rsplit("-", 2)[1]) for r in registros
                 if r["id"].endswith(f"-{filtros['ano']}") and r["decisao"] in ("aprovada", "editada")}
    quadro["acao_aprovada"] = quadro.cod_ibge.astype(int).isin(aprovados).map({True: "Sim", False: "Não"})
    tema.legenda(cfg, estimavel)
    oficial = cfg["risco"]["criterio_garantia_safra"]
    alerta = quadro.perda_estimada_pct.ge(filtros["limiar"])
    if not estimavel:
        alerta = quadro.classe.eq("critico")
    a, b, c, d = st.columns(4)
    with a:
        rotulo = (f"Municípios com perda ≥ {filtros['limiar']}%" if estimavel
                  else "Municípios com chuva muito abaixo do normal")
        legenda = (f"Limiar exploratório; critério oficial: {oficial}%"
                   if estimavel and filtros["limiar"] != oficial else "")
        kpi(rotulo, f"{alerta.sum()} de {len(quadro)}", legenda, cor="alerta" if alerta.any() else "seguro")
    with b:
        if estimavel:
            kpi("Maior perda", percentual(quadro.perda_estimada_pct.max(), 0), quadro.iloc[0].municipio, quadro.iloc[0].classe)
        else:
            kpi("Chuva mais abaixo do normal", percentual(quadro.anomalia_pct.min(), 0),
                f"{quadro.iloc[0].municipio} · perda estimada a partir de 1º/03", quadro.iloc[0].classe)
    with c:
        kpi("Pedidos de agricultores", f"{quadro.pedidos.sum():,}".replace(",", "."), "Pedidos da safra inteira")
        selo_simulado(simulado=cfg["fontes"]["pedidos"] != "rpa")
    with d:
        mediana_real = quadro.perda_producao_pct.median()
        kpi("Perda real (IBGE)", percentual(mediana_real, 0), "Mediana municipal · safra completa",
            classificar(mediana_real, cfg) if pd.notna(mediana_real) else "seguro")
        if filtros["ano"] > cfg["fontes"]["pam_fim"]:
            st.caption("Dados reais ainda não publicados (o IBGE publica a safra no ano seguinte)")
    mapa, lista = st.columns([2.1, 1])
    with mapa:
        st.slider("Reveja a safra mês a mês", inicio, fim, key="mes", format="Mês %d")
        st.caption(f"Até {corte:%d/%m/%Y} · {MESES[mes-1]} · pedidos da safra inteira")
        if not estimavel:
            st.markdown("**Cedo para estimar perda — sinal de chuva (anomalia × normal)**")
        if malhas:
            st.plotly_chart(mapa_perdas(quadro, malhas, cfg, cfg["interface"]["altura_mapa"]),
                            key="mapa_perdas", config={"displayModeBar": False},
                            alt="Municípios por perda estimada ou sinal de chuva. A lista ao lado traz os valores e as classes.")
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
                if estimavel:
                    st.write(f"Perda estimada {percentual(linha.perda_estimada_pct, 0)} · {chuva} · {linha.pedidos} pedidos")
                else:
                    st.write(f"{chuva.capitalize()} · {linha.pedidos} pedidos")
                    st.caption("Perda estimada a partir de 1º de março")
                selo_simulado(simulado=cfg["fontes"]["pedidos"] != "rpa")
                serie = dados.serie(int(linha.cod_ibge), filtros["ano"], versao)
                st.plotly_chart(grafico_chuva(serie.loc[serie.data.le(corte)], cfg["interface"]["altura_mini"],
                                compacto=True, cfg=cfg, cultura=filtros["cultura"], limiar=filtros["limiar"]),
                                key=f"mini_{linha.cod_ibge}", config={"displayModeBar": False})
                abrir_raio_x(linha.cod_ibge, f"panorama_abrir_{linha.cod_ibge}", "Ver por quê →")
    with st.expander("Todos os municípios · mês selecionado"):
        selo_simulado(simulado=cfg["fontes"]["pedidos"] != "rpa")
        st.dataframe(quadro.astype(object).where(pd.notna(quadro), "—")[[ "municipio", "uf", "perda_estimada_pct", "classe", "chuva_mm", "normal_mm", "pedidos"]].rename(
            columns={"municipio": "Município", "uf": "UF", "perda_estimada_pct": "Perda estimada (%)",
                     "classe": "Risco", "chuva_mm": "Chuva (mm)", "normal_mm": "Normal (mm)", "pedidos": "Pedidos"}),
                     hide_index=True, width="stretch")
    como_calculamos(cfg, filtros)
