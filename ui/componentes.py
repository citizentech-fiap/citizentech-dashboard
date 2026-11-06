"""Componentes pequenos compartilhados pelas telas de decisão."""
from html import escape

import streamlit as st
import pandas as pd

from state import store
from ui.tema import CORES, badge_html


def percentual(valor, casas=1):
    return f"{valor:.{casas}f}".replace(".", ",") + "%" if pd.notna(valor) else "—"


def selo_simulado(texto="simulado"):
    from providers.config import carregar
    if carregar()["fontes"]["pedidos"] != "rpa":
        st.html(f'<span class="selo-simulado" title="Pedidos de agricultores são simulados: dado pessoal não é público (LGPD). Em operação, vêm do robô de triagem.">{escape(texto)}</span>')


def kpi(titulo, valor, delta="", cor="seguro"):
    st.html(f'<div class="mandacaru-kpi" style="--cor:{CORES[cor]}">'
            f'<div class="rotulo">{escape(str(titulo))}</div>'
            f'<div class="valor">{escape(str(valor))}</div>'
            f'<div class="detalhe">{escape(str(delta))}</div></div>')


def badge_risco(classe):
    st.html(badge_html(classe))


def abrir_raio_x(codigo, chave, rotulo="Ver evidências no raio-x →"):
    st.button(rotulo, key=chave, on_click=store.abrir_municipio, args=(int(codigo),))


def cartao_recomendacao(rec, cfg, filtros):
    from pipelines.recomendacoes import ROTULOS_TIPOS
    from ui.acoes import renderizar as acoes, sugestao

    with st.container(border=True):
        st.caption(ROTULOS_TIPOS[rec.tipo])
        st.subheader(rec.municipio)
        badge_risco(rec.evidencias["classe"])
        selo_simulado()
        ev = rec.evidencias
        sinal = (f"Perda estimada {percentual(ev['perda_estimada_pct'], 0)}" if ev.get("estimavel", True)
                 else f"Chuva {percentual(ev['anomalia_pct'], 0)} × normal")
        st.write(f"{sinal} · {ev['familias_garantia_safra']} famílias no Garantia-Safra · {ev['travados_sem_caf']} sem CAF")
        st.caption(f"{ev['docs_completos']} com documentação completa")
        if not ev.get('estimavel', True):
            st.caption("Perda estimada a partir de 1º de março")
        campos = sugestao(rec, cfg)
        st.caption(f"Sugestão: seg {campos['data']:%d/%m} · {campos['local']} · {campos['plano']}")
        acoes(rec, cfg, filtros)
        with st.expander("Ver detalhes"):
            st.write(rec.justificativa)
            st.caption(rec.acao_sugerida)
            abrir_raio_x(rec.cod_ibge, f"evidencias_{rec.id}", "Ver no mapa/raio-x →")


def aviso_modelo():
    st.caption("ⓘ A perda estimada é uma aproximação acadêmica do indicador hídrico, relativa à normal 1991–2020. "
               "Não é laudo nem comprova direito ao Garantia-Safra. A decisão de vistoria e pagamento é humana e externa ao painel.")


def fontes():
    st.caption("Real: chuva (Open-Meteo/ERA5), mapas e produção agrícola (IBGE), "
               "pagamentos do Garantia-Safra (Portal da Transparência), regras (gov.br). "
               "Simulado: pedidos individuais de agricultores (dado pessoal, não público).")



def como_calculamos(cfg, filtros):
    with st.expander("Como calculamos"):
        aviso_modelo()
        st.write("A aproximação compara ISNA do ano e da normal, sem balanço de solo ou fenologia, "
                 "com resposta FAO-33. Faixa cinza: ETc acumulada do ano e da normal. "
                 "Perda (%) no eixo direito; a linha pontilhada é o critério oficial. "
                 "Quando diferente, a linha tracejada mostra o limiar de triagem.")
        st.write(f"{cfg['risco']['criterio_garantia_safra']}% é a referência oficial. Ajustar o limiar "
                 "explora prioridades; não muda as classes de risco nem aprova benefício. "
                 "Vistorias e convocações preservam as regras mínimas do modelo. Mutirões de CAF "
                 "dependem das pendências, mesmo sem seca.")
        st.write("Prioridade é relativa aos municípios e pedidos selecionados; não compare o score entre anos. "
                 "Decisões valem para o município e ano, mesmo ao trocar cultura ou serviço. "
                 "Triagem respondida não significa benefício concedido. O mês de replay vale apenas na aba 1; "
                 "os pedidos sintéticos são da safra inteira. A aba 2 analisa a safra completa.")
        st.caption(f"Cultura: {filtros['cultura']} · limiar de triagem: {filtros['limiar']}%. "
                   "A abertura usa snapshots locais. A atualização renova a safra das UFs selecionadas "
                   "e preserva a normal 1991–2020.")
        validacao_retrospectiva(cfg, filtros)


def validacao_retrospectiva(cfg, filtros):
    from state import dados
    from ui.graficos import dispersao_validacao
    try:
        placar = dados.validacao(filtros["cultura"], dados.versao_snapshots())
    except (OSError, ValueError):
        st.warning("Validação retrospectiva indisponível; recupere os dados locais.")
        return
    st.markdown("### Estimado × real · 2012–2025")
    st.write("O modelo usa só chuva e demanda hídrica. Perdas por pragas, preço ou área não plantada não aparecem. "
             "A referência do placar é a perda de produção do IBGE, nunca os pagamentos.")
    st.plotly_chart(dispersao_validacao(placar["dados"], cfg["interface"]["altura_chuva"]), key="validacao_retrospectiva")
    matriz = placar["matriz"]
    st.markdown(f"**Placar no critério de {cfg['risco']['criterio_garantia_safra']}%** "
                "(cada ponto é um município em uma safra)")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Acerto: perda", int(matriz.loc[True, True]))
    q2.metric("Acerto: sem perda", int(matriz.loc[False, False]))
    q3.metric("Perda não vista", int(matriz.loc[False, True]))
    q4.metric("Alarme falso", int(matriz.loc[True, False]))
    correlacao = f"{placar['spearman']:.2f}".replace(".", ",") if pd.notna(placar['spearman']) else "indisponível"
    st.caption(f"Critério {cfg['risco']['criterio_garantia_safra']}% · Acurácia: {percentual(placar['acuracia'] * 100)} · "
               f"Spearman: {correlacao}")
    st.caption(f"{placar['pares_validos']} pares válidos · {placar['pares_excluidos']} excluídos por falta de medida.")
    st.markdown("**Maiores divergências**")
    st.dataframe(placar["divergencias"][["municipio", "uf", "ano", "perda_estimada_pct", "perda_producao_pct", "divergencia_pp"]]
                 .rename(columns={"municipio": "Município", "uf": "UF", "ano": "Safra",
                                  "perda_estimada_pct": "Estimada (%)", "perda_producao_pct": "Real IBGE (%)",
                                  "divergencia_pp": "Diferença (p.p.)"}).round(0),
                 hide_index=True, column_config={"Safra": st.column_config.NumberColumn(format="%d")})
    for aviso in placar["avisos"]:
        st.warning(aviso)
