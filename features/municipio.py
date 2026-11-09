"""Raio-x: evidências climáticas e obstáculos de atendimento municipais."""
import pandas as pd
import streamlit as st

from features.metodo import como_calculamos
from pipelines.demanda import por_servico
from pipelines.risco import classificar
from features.decisoes import acoes_municipio
from state import dados, store
from ui.componentes import badge_risco, kpi, percentual, selo_simulado
from ui.graficos import barras_documentos, barras_servicos, calendario_seco, grafico_chuva, producao_real


def renderizar(ctx, cfg, filtros, versao):
    quadro = ctx["quadro"].sort_values("municipio")
    codigos = quadro.cod_ibge.astype(int).tolist()
    if store.obter("municipio") not in codigos:
        store.definir("municipio", codigos[0])
    nomes = quadro.set_index("cod_ibge").apply(lambda r: f"{r.municipio} / {r.uf}", axis=1).to_dict()
    store.definir("_municipio", store.obter("municipio"))
    st.selectbox("Município", codigos, key="_municipio", format_func=nomes.get,
                 on_change=store.selecionar_municipio)
    codigo = store.obter("municipio")
    linha = quadro.loc[quadro.cod_ibge.eq(codigo)].iloc[0]
    st.subheader(f"{linha.municipio}: o que exige atenção?")
    badge_risco(linha.classe)
    st.caption(f"Safra completa {filtros['ano']} · {cfg['modelo_hidrico']['culturas'][filtros['cultura']]['nome']}")
    a, b, c, d = st.columns(4)
    with a:
        kpi("Perda estimada", percentual(linha.perda_estimada_pct, 0), cor=linha.classe)
        if not linha.estimavel:
            st.caption("estimativa a partir de 1º de março")
    with b:
        comparacao = (f"{abs(linha.anomalia_pct):.0f}% {'abaixo' if linha.anomalia_pct < 0 else 'acima'} do normal"
                      if linha.anomalia_pct == linha.anomalia_pct else "normal indisponível")  # NaN != NaN
        kpi("Chuva da safra", f"{linha.chuva_mm:.0f} mm", f"{comparacao} ({linha.normal_mm:.0f} mm)",
            _cor_faixa(-linha.anomalia_pct, (0, 20, 40)))
    with c:
        kpi("Maior sequência sem chuva", f"{linha.maior_seca_dias} dias", f"Menos de {cfg['modelo_hidrico']['dia_seco_mm']:g} mm por dia",
            _cor_faixa(linha.maior_seca_dias, (15, 30, 60)))
    with d:
        kpi("Agricultores sem CAF", str(linha.travados_sem_caf), "Pedidos travados", "alerta" if linha.travados_sem_caf else "seguro")
        selo_simulado(simulado=cfg["fontes"]["pedidos"] != "rpa")
    retrospectiva(codigo, linha, cfg, filtros, versao)
    with st.spinner("Preparando as evidências do município…"):
        serie = dados.serie(codigo, filtros["ano"], versao)
        ev = dados.evolucao(filtros["ano"], filtros["cultura"], versao)
    st.markdown("### A chuva foi suficiente para a cultura?")
    st.caption("Compare a chuva da safra com a chuva normal e a água que a plantação precisa.")
    st.plotly_chart(grafico_chuva(serie, cfg["interface"]["altura_chuva"], compacto=False, cfg=cfg,
                    cultura=filtros["cultura"], limiar=filtros["limiar"], evolucao=ev.loc[ev.cod_ibge.eq(codigo)]), key="chuva_municipio")
    pedidos = ctx["pedidos"].loc[ctx["pedidos"].cod_ibge.eq(codigo)]
    resumo = ctx["demanda"].loc[ctx["demanda"].cod_ibge.eq(codigo)]
    # calendário em largura total (em meia coluna os quadradinhos ficam ilegíveis); barras lado a lado
    st.markdown("### Quando faltou chuva?")
    figura = calendario_seco(serie, cfg["modelo_hidrico"]["dia_seco_mm"])
    st.pyplot(figura, width="stretch")
    figura.clear()
    st.caption("Cada quadrado é um dia. Verde: com chuva; laranja: seco.")
    st.markdown("### O que impede o atendimento?")
    selo_simulado(simulado=cfg["fontes"]["pedidos"] != "rpa")
    st.caption(f"{len(pedidos)} pedidos · serviço selecionado na barra lateral")
    colunas = st.columns(2)
    for coluna, (titulo, fig) in zip(colunas, (
            ("Pedidos por serviço", barras_servicos(por_servico(pedidos), cfg["interface"]["altura_barras"])),
            ("Documento que mais falta", barras_documentos(resumo, cfg["interface"]["altura_barras"])))):
        with coluna:
            st.markdown(f"**{titulo}**")
            if fig is None:
                st.info("Sem pendências ou pedidos nos filtros selecionados.")
            else:
                st.plotly_chart(fig, key=f"municipio_{titulo}")
    acoes_municipio(ctx, cfg, filtros, codigo, linha.municipio)
    como_calculamos(cfg, filtros)


def _cor_faixa(valor, limites):
    """Cor semântica para um indicador em que maior = pior: limites (atenção, alerta, crítico)."""
    if valor != valor:  # NaN: sem normal para comparar
        return "seguro"
    atencao, alerta, critico = limites
    if valor >= critico:
        return "critico"
    if valor >= alerta:
        return "alerta"
    return "atencao" if valor > atencao else "seguro"


def retrospectiva(codigo, linha, cfg, filtros, versao):
    st.markdown("### O que aconteceu de fato")
    ano = filtros["ano"]
    if ano > cfg["fontes"]["pam_fim"]:
        st.info("Dados reais ainda não publicados (o IBGE publica a safra no ano seguinte)")
    else:
        try:
            real = dados.perda_real(filtros["cultura"], versao)
            municipal = real.loc[real.cod_ibge.eq(codigo)]
            st.plotly_chart(producao_real(municipal, ano, cfg["realidade"]["anos_media"],
                            cfg["interface"]["altura_chuva"]), key="producao_real")
            atual = municipal.loc[municipal.ano.eq(ano), "perda_producao_pct"]
            valor = atual.iloc[0] if not atual.empty else float("nan")
            st.caption(f"Produção de {filtros['cultura']} (IBGE/PAM) · safra {ano} em vermelho")
            r1, r2 = st.columns(2)
            with r1:
                kpi("Perda real (IBGE)", percentual(valor, 0), "produção × média dos dez anos anteriores",
                    classificar(valor, cfg) if pd.notna(valor) else "seguro")
            with r2:
                kpi("Perda estimada pelo painel", percentual(linha.perda_estimada_pct, 0), "só chuva (modelo hídrico)",
                    linha.classe)
            st.caption("Perda real relativa à produção média dos dez anos anteriores; retrospectiva, sem alterar prioridades.")
        except (OSError, ValueError):
            st.warning("Produção IBGE indisponível no arquivo local.")
    st.caption(f"Famílias pagas entre jul/{ano} e jun/{ano+1} (Portal da Transparência)")
    st.caption("Convenção analítica; o arquivo não informa ano-safra e há atrasos. Pagamentos não comprovam acerto ou erro do modelo.")
    try:
        pagos = dados.pagamentos(versao)
        pagos = pagos.loc[pagos.cod_ibge.eq(codigo) & pagos.safra.eq(ano)]
        completa = dados.cobertura_pagamentos(ano, versao)
        if not completa:
            st.warning("Cobertura de pagamentos da safra incompleta; ausência de registro não significa ausência de pagamento.")
        if not pagos.empty:
            st.write(f"{int(pagos.familias.sum())} famílias pagas · R$ {pagos.valor_total.sum():,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
        elif completa:
            st.write("Sem pagamentos registrados no período completo.")
        else:
            st.write("Pagamentos não disponíveis para este município no recorte.")
    except (OSError, ValueError):
        st.warning("Pagamentos indisponíveis; recupere o arquivo local.")
