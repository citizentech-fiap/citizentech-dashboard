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


def cartao_recomendacao(rec):
    from pipelines.recomendacoes import ROTULOS_TIPOS
    st.caption(f"PRIORIDADE {rec.prioridade:.0%} · {ROTULOS_TIPOS.get(rec.tipo, rec.tipo).upper()}")
    st.subheader(rec.titulo)
    badge_risco(rec.evidencias["classe"])
    st.write(rec.justificativa)
    st.caption(rec.acao_sugerida)
    abrir_raio_x(rec.cod_ibge, f"evidencias_{rec.id}")


def aviso_modelo():
    st.caption("ⓘ A perda estimada é uma aproximação acadêmica do indicador hídrico, relativa à normal 1991–2020. "
               "Não é laudo nem comprova direito ao Garantia-Safra. A decisão de vistoria e pagamento é humana e externa ao painel.")


def fontes():
    st.caption("Clima real: [Open-Meteo Archive](https://open-meteo.com/) (CC BY 4.0, reanálise). "
               "Polígonos: [IBGE](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3). "
               "Referência: 1991–2020. Pedidos da demonstração: sintéticos, sem dados pessoais.")
