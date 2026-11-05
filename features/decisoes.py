"""Mesa humana: proposta, revisão de mensagem e auditoria local."""
from datetime import date

import pandas as pd
import streamlit as st

from state import dados, store
from ui.componentes import cartao_recomendacao, kpi


def _contexto(filtros):
    return (f"Safra {filtros['ano']} · cultura {filtros['cultura']} · serviço {filtros['servico']} · "
            f"limiar de triagem {filtros['limiar']}%")


def _registrar(rec, escolha, justificativa, mensagem, usuario):
    try:
        dados.salvar_decisao(rec, escolha, justificativa, mensagem, usuario)
    except (OSError, ValueError):
        st.error("Não foi possível gravar a decisão. Confira a identificação do gestor e o histórico local antes de tentar novamente. Sua revisão permanece nesta tela.")
        return
    store.guardar_rascunho(rec.id, None)
    detalhe = " Mensagem salva em output/convocacoes/; nenhum envio realizado." if rec.tipo != "vistoria" and escolha != "rejeitada" else ""
    store.definir("notificacao", f"Decisão {escolha} para {rec.municipio}, registrada na auditoria.{detalhe}")
    st.rerun()


def _revisar(rec, rascunho, usuario):
    st.markdown("#### Revise antes de confirmar")
    st.info("Rascunho para revisão. A decisão e a mensagem só serão salvas após sua confirmação. Nada será enviado.")
    st.caption(rascunho["motivo_rag"])
    with st.form(f"revisar_{rec.id}"):
        mensagem = st.text_area("Mensagem aos agricultores", value=rascunho["mensagem"],
                                height=230, key=f"mensagem_{rec.id}")
        revisada = st.checkbox("Revisei data, local e texto da mensagem", key=f"revisada_{rec.id}")
        confirmar = st.form_submit_button("Confirmar e salvar", type="primary", key=f"confirmar_{rec.id}")
        voltar = st.form_submit_button("Voltar à edição", key=f"voltar_{rec.id}")
    if voltar:
        store.definir("retomar_edicao", (rec.id, rascunho["campos"]))
        store.guardar_rascunho(rec.id, None)
        st.rerun()
    if confirmar:
        if not revisada or not mensagem.strip():
            st.error("Revise o texto e marque a confirmação antes de salvar.")
            return
        escolha = "editada" if mensagem != rascunho["mensagem"] else rascunho["escolha"]
        _registrar(rec, escolha, rascunho["justificativa"], mensagem, usuario)


def _formulario(rec, filtros, usuario):
    contexto = _contexto(filtros)
    rascunho = store.obter("rascunhos").get(rec.id)
    if rascunho and rascunho["contexto"] != contexto:
        store.guardar_rascunho(rec.id, None)
        st.warning("O recorte mudou. Prepare um novo rascunho com os filtros atuais.")
        rascunho = None
    if rascunho:
        _revisar(rec, rascunho, usuario)
        return
    retomar = store.obter("retomar_edicao")
    if retomar and retomar[0] == rec.id:
        for chave, valor in retomar[1].items():
            store.definir(f"{chave}_{rec.id}", valor)
        store.definir("retomar_edicao", None)
    chave_plano = f"plano_{rec.id}"
    if store.obter(chave_plano) is None:
        store.definir(chave_plano, rec.acao_sugerida)
    with st.form(f"decidir_{rec.id}"):
        st.caption("Confirme a proposta ou edite o plano. Para rejeitar, explique o motivo.")
        a, b = st.columns(2)
        with a:
            data = st.date_input("Data da ação", value=None, min_value=date.today(),
                                 key=f"data_{rec.id}", format="DD/MM/YYYY")
        with b:
            local = st.text_input("Local e horário", key=f"local_{rec.id}", placeholder="Ex.: sede da EMATER, às 9h")
        texto = st.text_area("Plano da ação", value=None, key=chave_plano)
        justificativa = st.text_area("Justificativa (obrigatória ao rejeitar)", key=f"justificativa_{rec.id}")
        a, b, c = st.columns(3)
        with a:
            aprovar = st.form_submit_button("Aprovar", type="primary", key=f"aprovar_{rec.id}")
        with b:
            editar = st.form_submit_button("Salvar edição", key=f"editar_{rec.id}")
        with c:
            rejeitar = st.form_submit_button("Rejeitar", key=f"rejeitar_{rec.id}")
    if not any((aprovar, editar, rejeitar)):
        return
    if not usuario.strip():
        st.error("Informe a identificação funcional do gestor.")
        return
    if rejeitar:
        if not justificativa.strip():
            st.error("Explique o motivo da rejeição; o campo justificativa é obrigatório.")
            return
        _registrar(rec, "rejeitada", f"{justificativa.strip()}\n{contexto}", "", usuario)
        return
    if data is None or not local.strip() or not texto.strip():
        st.error("Informe data, local, horário e plano da ação antes de aprovar ou salvar a edição.")
        return
    escolha = "editada" if editar or texto.strip() != rec.acao_sugerida else "aprovada"
    justificativa_original = justificativa
    justificativa = f"{justificativa.strip() or rec.justificativa}\n{contexto}"
    logistica = f"Data: {data:%d/%m/%Y}\nLocal e horário: {local.strip()}\nPlano: {texto.strip()}"
    if rec.tipo == "vistoria":
        _registrar(rec, escolha, justificativa, logistica, usuario)
        return
    lugar = st.empty()
    lugar.info("▰ ▰ ▰ Preparando o texto para sua revisão…")
    with st.spinner("Consultando o assistente e preparando a convocação…"):
        mensagem, motivo = dados.rascunhar(rec)
    lugar.empty()
    # O template também é submetido à mesma revisão humana do texto do RAG.
    mensagem = mensagem.replace("Data, horário e local: a confirmar pelo gestor.", logistica)
    store.guardar_rascunho(rec.id, {"escolha": escolha, "justificativa": justificativa,
                           "mensagem": mensagem, "motivo_rag": motivo, "contexto": contexto,
                           "campos": {"data": data, "local": local, "plano": texto, "justificativa": justificativa_original}})
    st.rerun()


def renderizar(ctx, cfg, filtros):
    st.subheader("Da evidência à ação")
    st.caption("A proposta é do painel. A decisão é sua. Nenhuma mensagem é enviada automaticamente.")
    try:
        historico = dados.historico()
    except (OSError, ValueError):
        st.error("Não foi possível ler o histórico de auditoria. Recupere o arquivo antes de registrar novas decisões.")
        return
    decididas = {r["id"] for r in historico}
    fila = [r for r in ctx["recomendacoes"] if r.id not in decididas]
    oficial = cfg["risco"]["criterio_garantia_safra"]
    if not ctx["quadro"].perda_estimada_pct.ge(oficial).any():
        st.success(f"Nenhum município atingiu o critério de {oficial}% nesta safra")
        st.caption("Uma safra dentro da normal também é um bom resultado. Pendências de CAF ainda podem justificar atendimento administrativo.")
    a, b = st.columns(2)
    with a:
        kpi("Ações aguardando você", len(fila), "Ordenadas por risco e demanda", "alerta" if fila else "seguro")
    with b:
        kpi("Decisões no recorte", sum(r.id in decididas for r in ctx["recomendacoes"]), "Registro permanente · por município e ano")
    usuario = st.text_input("Identificação funcional do gestor", value="coordenacao-demo", key="gestor",
                            help="Use um identificador funcional, sem nome pessoal. Na demonstração, mantenha coordenacao-demo.")
    st.caption("Prioridade é relativa aos municípios e pedidos selecionados; não compare o score entre anos. Decisões valem para o município e ano, mesmo ao trocar cultura ou serviço.")
    if not fila:
        st.info("Nenhuma ação pendente neste recorte. Consulte o histórico ou amplie os filtros.")
    else:
        tamanho = cfg["interface"]["recomendacoes_por_pagina"]
        paginas = list(range(1, (len(fila) - 1) // tamanho + 2))
        pagina = st.selectbox("Página de recomendações", paginas, format_func=lambda p: f"{p} de {len(paginas)}")
        for rec in fila[(pagina - 1) * tamanho:pagina * tamanho]:
            with st.container(border=True):
                cartao_recomendacao(rec)
                _formulario(rec, filtros, usuario)
    st.markdown("### Histórico de decisões")
    municipios = set(ctx["quadro"].municipio)
    registros = [r for r in historico if r["id"].endswith(f"-{filtros['ano']}") and r["municipio"] in municipios]
    st.caption("Histórico do ano e UFs selecionados, incluindo recomendações que já saíram da fila. Abra a justificativa e a mensagem para conferir o contexto de cultura e serviço da decisão.")
    if registros:
        tabela = pd.DataFrame(registros).iloc[::-1]
        st.dataframe(tabela[["quando", "municipio", "tipo", "decisao", "usuario", "justificativa", "mensagem"]],
                     hide_index=True, width="stretch")
        st.download_button("Baixar histórico deste recorte (CSV)", tabela.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"decisoes-{filtros['ano']}.csv", mime="text/csv")
    else:
        st.caption("As decisões aprovadas, editadas ou rejeitadas aparecerão aqui.")
