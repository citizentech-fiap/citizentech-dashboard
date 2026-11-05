"""Interação reutilizada nos cartões: sugestão, ajuste, recusa e revisão humana."""
from datetime import date, timedelta

import streamlit as st

from state import dados, store


def sugestao(rec, cfg):
    hoje = date.today()
    proxima = hoje + timedelta(days=(cfg["decisoes"]["dia_semana_sugerido"] - hoje.weekday()) % 7)
    return {"data": proxima, "local": cfg["decisoes"]["local_sugerido"].format(municipio=rec.municipio),
            "plano": rec.acao_sugerida, "justificativa": ""}


def _registrar(rec, escolha, justificativa, mensagem, cfg):
    try:
        dados.salvar_decisao(rec, escolha, justificativa, mensagem, cfg["decisoes"]["usuario_padrao"])
    except (OSError, ValueError):
        st.error("Não foi possível gravar a decisão. Confira o histórico e tente novamente. Sua revisão foi preservada.")
        return
    store.guardar_rascunho(rec.id, None)
    store.formulario(rec.id, {})
    store.definir("notificacao", f"Decisão registrada para {rec.municipio}.")
    st.rerun()


def _preparar(rec, campos, escolha, cfg, filtros):
    if campos["data"] is None or campos["data"] < date.today() or not campos["local"].strip() or not campos["plano"].strip():
        st.error("Informe data a partir de hoje, local, horário e plano da ação.")
        return
    contexto = (f"Safra {filtros['ano']} · cultura {filtros['cultura']} · serviço {filtros['servico']} · "
                f"alerta a partir de {filtros['limiar']}%")
    justificativa = f"{campos['justificativa'].strip() or rec.justificativa}\n{contexto}"
    logistica = (f"Data: {campos['data']:%d/%m/%Y}\nLocal e horário: {campos['local'].strip()}\n"
                 f"Plano: {campos['plano'].strip()}")
    if rec.tipo != "convocacao":
        _registrar(rec, escolha, justificativa, logistica, cfg)
        return
    lugar = st.empty()
    lugar.info("▰ ▰ ▰ Preparando o texto para sua revisão…")
    with st.spinner("Preparando a convocação…"):
        mensagem, motivo = dados.rascunhar(rec)
    lugar.empty()
    mensagem = mensagem.replace("Data, horário e local: a confirmar pelo gestor.", logistica)
    store.guardar_rascunho(rec.id, {"escolha": escolha, "justificativa": justificativa,
                                   "mensagem": mensagem, "motivo_rag": motivo, "campos": campos})
    st.rerun()


def _revisar(rec, rascunho, cfg):
    st.caption("Revise a mensagem antes de confirmar. Ela será salva como rascunho, sem envio automático.")
    with st.form(f"revisar_{rec.id}"):
        mensagem = st.text_area("Mensagem aos agricultores", value=rascunho["mensagem"],
                                height=230, key=f"mensagem_{rec.id}")
        revisada = st.checkbox("Revisei data, local e texto da mensagem", key=f"revisada_{rec.id}")
        confirmar = st.form_submit_button("Confirmar convocação", type="primary", key=f"confirmar_{rec.id}")
        voltar = st.form_submit_button("Voltar à edição", key=f"voltar_{rec.id}")
    if voltar:
        store.formulario(rec.id, {"modo": "ajustar", "campos": rascunho["campos"]})
        store.guardar_rascunho(rec.id, None)
        st.rerun()
    if confirmar:
        if not revisada or not mensagem.strip():
            st.error("Revise o texto e marque a confirmação antes de salvar.")
            return
        escolha = "editada" if mensagem != rascunho["mensagem"] else rascunho["escolha"]
        _registrar(rec, escolha, rascunho["justificativa"], mensagem, cfg)


def renderizar(rec, cfg, filtros):
    a, b, c = st.columns(3)
    with a:
        aprovar = st.button("Aprovar", type="primary", key=f"aprovar_{rec.id}")
    with b:
        ajustar = st.button("Ajustar", key=f"ajustar_{rec.id}")
    with c:
        recusar = st.button("Recusar", key=f"recusar_{rec.id}")
    if aprovar:
        _preparar(rec, sugestao(rec, cfg), "aprovada", cfg, filtros)
    if ajustar or recusar:
        anterior = store.formulario(rec.id) or {}
        store.formulario(rec.id, {"modo": "ajustar" if ajustar else "recusar",
                                  "campos": anterior.get("campos", sugestao(rec, cfg))})
        store.guardar_rascunho(rec.id, None)
    rascunho = store.obter("rascunhos").get(rec.id)
    if rascunho:
        _revisar(rec, rascunho, cfg)
        return
    formulario = store.formulario(rec.id) or {}
    modo = formulario.get("modo")
    if modo == "recusar":
        with st.form(f"recusa_{rec.id}"):
            motivo = st.text_area("Motivo da recusa (obrigatório)", key=f"motivo_{rec.id}")
            confirmar = st.form_submit_button("Confirmar recusa", key=f"confirmar_recusa_{rec.id}")
        if confirmar:
            if not motivo.strip():
                st.error("Explique o motivo da recusa; o motivo é obrigatório.")
            else:
                contexto = f"Safra {filtros['ano']} · cultura {filtros['cultura']} · serviço {filtros['servico']} · alerta {filtros['limiar']}%"
                _registrar(rec, "rejeitada", f"{motivo.strip()}\n{contexto}", "", cfg)
    elif modo == "ajustar":
        campos = formulario["campos"]
        with st.form(f"ajuste_{rec.id}"):
            a, b = st.columns(2)
            with a:
                data = st.date_input("Data da ação", value=campos["data"], min_value=date.today(),
                                     key=f"data_{rec.id}", format="DD/MM/YYYY")
            with b:
                local = st.text_input("Local e horário", value=campos["local"], key=f"local_{rec.id}")
            plano = st.text_area("Plano da ação", value=campos["plano"], key=f"plano_{rec.id}")
            justificativa = st.text_area("Justificativa do ajuste", value=campos["justificativa"], key=f"justificativa_{rec.id}")
            salvar = st.form_submit_button("Salvar ajuste", type="primary", key=f"salvar_ajuste_{rec.id}")
        if salvar:
            campos = dict(data=data, local=local, plano=plano, justificativa=justificativa)
            store.formulario(rec.id, {"modo": "ajustar", "campos": campos})
            _preparar(rec, campos, "editada", cfg, filtros)
