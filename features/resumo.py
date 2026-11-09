"""Resumo revisável, com fatos auditáveis e cache por conteúdo na sessão."""
import hashlib
import json

import pandas as pd
import streamlit as st

from pipelines import resumo
from state import dados, store
from ui.graficos import barras_contagens

SYSTEM = ("Você escreve o resumo semanal para a coordenação do Garantia-Safra. "
          "Use SOMENTE os fatos em JSON. Não invente números nem relações causais. "
          "Quando citar travados sem CAF, diga que o dado é simulado se 'simulado' for verdadeiro. "
          "Só fale de perda real (IBGE) se o campo 'realidade' existir; ela é retrospectiva. "
          "Se 'estimavel' for falso, fale em sinal de chuva, não em perda. "
          "Nunca cite nomes de campos do JSON nem explique as regras acima. "
          "Máximo 180 palavras, português simples, sem markdown. "
          "Termine com três próximas ações concretas, uma por linha, citando municípios ou quantidades dos fatos; "
          "vistorias de perdas vêm primeiro, porque sem laudo não há pagamento.")


def renderizar(ctx, cfg, filtros):
    st.subheader("Resumo da semana")
    st.caption(f"Safra {filtros['ano']} · serviço {filtros['servico']} · revise antes de compartilhar.")
    corte = f"{filtros['ano']}-{cfg['safra']['fim_mes_dia']}"
    try:
        real = dados.perda_real(filtros['cultura'], dados.versao_snapshots())
        historico = dados.historico()
    except (OSError, ValueError):
        st.warning("Não foi possível ler os dados retrospectivos ou o histórico para o resumo.")
        return
    fatos = resumo.fatos(ctx['quadro'], ctx['demanda'], ctx['recomendacoes'], historico,
                         cfg, filtros['ano'], corte, real)
    contagens = pd.DataFrame(fatos["municipios_por_classe"].items(), columns=["categoria", "quantidade"])
    figura = barras_contagens(contagens, cfg["interface"]["altura_barras"])
    if figura is not None:
        st.caption("Municípios por classe de risco · filtros selecionados")
        st.plotly_chart(figura, key="grafico_resumo")
    else:
        st.info("Sem municípios para resumir.")
    payload = json.dumps(fatos, ensure_ascii=False, sort_keys=True, allow_nan=False)
    chave = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    cache = dict(store.obter('resumos', {}))
    if st.button("Gerar resumo da semana", key="gerar_resumo", type="primary") and chave not in cache:
        with st.spinner("Preparando o resumo…"):
            texto, motivo = dados.gerar_texto(SYSTEM, payload)
        cache[chave] = dict(texto=texto or resumo.template(fatos), ia=bool(texto), motivo=motivo)
        store.definir('resumos', cache)
    registro = cache.get(chave)
    if registro:
        widget = f'resumo_texto_{chave}'
        texto_atual = store.obter(widget, registro['texto'])
        desconhecidos = resumo.numeros_desconhecidos(texto_atual, fatos)
        if desconhecidos:
            st.warning("Números fora dos fatos: " + ', '.join(desconhecidos) + ". Revise ou use o resumo sem IA.")
        if st.button("Usar resumo sem IA (template)", key="template_resumo"):
            registro = dict(texto=resumo.template(fatos), ia=False, motivo='')
            cache[chave] = registro
            store.definir('resumos', cache)
            store.definir(widget, registro['texto'])
        st.caption("Gerado por IA — revise antes de enviar" if registro['ia'] else "Resumo automático sem IA")
        if registro['motivo']:
            st.info(registro['motivo'])
        if store.obter(widget) is None:
            store.definir(widget, registro['texto'])
        texto = st.text_area("Revise o resumo", key=widget, height=240)
        registro['texto'] = texto
        cache[chave] = registro
        store.definir('resumos', cache)
        store.definir('ultimo_resumo', texto)
        st.download_button("Baixar .txt", texto.encode('utf-8'), file_name=f"resumo-{filtros['ano']}.txt", mime="text/plain")
    with st.expander("Fatos usados"):
        st.json(resumo.fatos_exibicao(fatos))
