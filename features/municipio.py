"""Raio-x: evidências climáticas e obstáculos de atendimento municipais."""
import streamlit as st

from pipelines.demanda import por_servico
from state import dados, store
from ui.componentes import badge_risco, kpi
from ui.graficos import barras_documentos, barras_servicos, calendario_seco, grafico_chuva


def renderizar(ctx, cfg, filtros, versao):
    quadro = ctx["quadro"].sort_values("municipio")
    codigos = quadro.cod_ibge.astype(int).tolist()
    if store.obter("municipio") not in codigos:
        store.definir("municipio", codigos[0])
    nomes = quadro.set_index("cod_ibge").apply(lambda r: f"{r.municipio} / {r.uf}", axis=1).to_dict()
    store.definir("_municipio", store.obter("municipio"))
    st.selectbox("Município para investigar", codigos, key="_municipio", format_func=nomes.get,
                 on_change=store.selecionar_municipio)
    codigo = store.obter("municipio")
    linha = quadro.loc[quadro.cod_ibge.eq(codigo)].iloc[0]
    st.subheader(f"{linha.municipio}: o que exige atenção?")
    badge_risco(linha.classe)
    st.caption(f"Safra completa {filtros['ano']} · {cfg['modelo_hidrico']['culturas'][filtros['cultura']]['nome']} · limiar de triagem {filtros['limiar']}%")
    a, b, c, d = st.columns(4)
    with a:
        kpi("Perda estimada", f"{linha.perda_estimada_pct:.1f}%", "Acima do limiar" if linha.perda_estimada_pct >= filtros["limiar"] else "Abaixo do limiar", linha.classe)
    with b:
        kpi("Chuva × normal", f"{linha.chuva_mm:.0f} mm", f"Normal {linha.normal_mm:.0f} mm · {linha.anomalia_pct:+.0f}%")
    with c:
        kpi("Maior sequência seca", f"{linha.maior_seca_dias} dias", f"Chuva < {cfg['modelo_hidrico']['dia_seco_mm']:g} mm/dia", "atencao")
    with d:
        kpi("Travados sem CAF", str(linha.travados_sem_caf), "Pedidos sintéticos GS / Pronaf", "alerta" if linha.travados_sem_caf else "seguro")
    with st.spinner("Preparando as evidências do município…"):
        serie = dados.serie(codigo, filtros["ano"], versao)
        ev = dados.evolucao(filtros["ano"], filtros["cultura"], versao)
    st.markdown("### A chuva foi suficiente para a cultura?")
    st.plotly_chart(grafico_chuva(serie, cfg["interface"]["altura_chuva"], compacto=False, cfg=cfg,
                    cultura=filtros["cultura"], limiar=filtros["limiar"], evolucao=ev.loc[ev.cod_ibge.eq(codigo)]), key="chuva_municipio")
    st.caption("Faixa cinza: ETc acumulada do ano e da normal. Perda (%) no eixo direito; a linha pontilhada é o critério oficial. Quando diferente, a linha tracejada mostra o limiar de triagem. A aproximação compara ISNA do ano e da normal, sem balanço de solo ou fenologia.")
    st.markdown("### Quando faltou chuva?")
    figura = calendario_seco(serie, cfg["modelo_hidrico"]["dia_seco_mm"])
    st.pyplot(figura, width="stretch")
    figura.clear()
    st.caption("Cada célula é um dia; posições vazias não existem no calendário. Verde: dia com chuva; laranja: dia seco.")
    pedidos = ctx["pedidos"].loc[ctx["pedidos"].cod_ibge.eq(codigo)]
    resumo = ctx["demanda"].loc[ctx["demanda"].cod_ibge.eq(codigo)]
    st.markdown("### O que impede o atendimento?")
    st.caption(f"{len(pedidos)} pedidos sintéticos · serviço selecionado na barra lateral. Triagem respondida não significa benefício concedido.")
    for coluna, titulo, fig in zip(st.columns(2), ("Pedidos por serviço", "Documentos faltantes"),
                                  (barras_servicos(por_servico(pedidos), cfg["interface"]["altura_barras"]),
                                   barras_documentos(resumo, cfg["interface"]["altura_barras"]))):
        with coluna:
            st.markdown(f"**{titulo}**")
            if fig is None:
                st.info("Sem pendências ou pedidos neste recorte.")
            else:
                st.plotly_chart(fig, key=f"municipio_{titulo}")
    st.button("Levar evidências à mesa de decisão →", key="municipio_mesa", on_click=store.definir,
              args=("aba", store.ABAS[2]))
