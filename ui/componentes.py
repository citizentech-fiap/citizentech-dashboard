"""Componentes pequenos compartilhados pelas telas de decisão."""
from html import escape

import streamlit as st

from state import store
from ui.tema import CORES, badge_html


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
        st.caption(ROTULOS_TIPOS[rec.tipo])  # a origem sintética dos pedidos já aparece nos cartões de resumo
        st.subheader(rec.municipio)
        badge_risco(rec.evidencias["classe"])
        ev = rec.evidencias
        st.write(f"Perda estimada {ev['perda_estimada_pct']:.0f}% · "
                 f"{ev['familias_garantia_safra']} famílias no Garantia-Safra · {ev['travados_sem_caf']} sem CAF")
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
    st.caption("Clima real: [Open-Meteo Archive](https://open-meteo.com/) (CC BY 4.0, reanálise). "
               "Polígonos: [IBGE](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3). "
               "Referência: 1991–2020. Pedidos da demonstração: sintéticos, sem dados pessoais.")


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
        fontes()
