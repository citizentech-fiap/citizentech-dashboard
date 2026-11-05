"""Chat com fontes do genAI, aberto explicitamente e isolado por recorte."""
from urllib.parse import urlparse

import streamlit as st

from state import dados, store


def _fontes(citacoes):
    if not citacoes:
        return
    st.caption("Fontes consultadas")
    for fonte in citacoes:
        titulo = f"[{fonte.get('n', '?')}] {fonte.get('titulo') or 'Fonte do serviço'}"
        url = fonte.get("url", "")
        if urlparse(url or "").scheme in ("https", "http"):
            st.link_button(titulo, url)
        else:
            st.caption(titulo)
        if fonte.get("secao"):
            st.caption(fonte["secao"])


def renderizar(ctx, cfg, filtros):
    st.subheader("Tire dúvidas sobre o atendimento")
    st.write("Consulte documentos e regras dos serviços antes de orientar o atendimento.")
    st.caption(f"Contexto: safra {filtros['ano']} · {filtros['cultura']} · UFs {', '.join(filtros['ufs'])} · "
               f"serviço {filtros['servico'].replace('_', ' ')}.")
    st.caption("Consulte regras e documentos dos serviços. Para decidir onde agir, use as etapas 1 e 2. Não informe dados pessoais.")
    exemplo = "Quais documentos levar para o Garantia-Safra?"
    st.button(exemplo, key="exemplo_pergunta", on_click=store.enviar_exemplo, args=(exemplo,))
    if not store.obter("rag_ativado"):
        st.button("Ativar assistente (leva uns 20 s na primeira vez)", key="conectar_rag", type="primary", on_click=store.definir,
                  args=("rag_ativado", True))
        return
    with st.spinner("Preparando a base de fontes do assistente…"):
        rag, motivo, _ = dados.recurso_rag()
    indisponivel = rag is None or not getattr(getattr(rag, "llm", None), "available", True)
    if indisponivel:
        st.warning("Assistente indisponível no momento. As evidências do painel e os rascunhos por template continuam disponíveis.")
        st.caption(motivo if rag is None else "O modelo de linguagem não está disponível nesta sessão.")
    contexto = (filtros["ano"], filtros["cultura"], filtros["ufs"], filtros["servico"], filtros["limiar"])
    historico = store.obter("conversas").get(contexto, [])
    for mensagem in historico:
        with st.chat_message(mensagem["role"]):
            st.write(mensagem["content"])
            _fontes(mensagem.get("citations", []))
    pergunta = st.chat_input("Pergunte sobre o serviço selecionado…", disabled=indisponivel,
                             max_chars=cfg["interface"]["chat_max_caracteres"])
    pergunta_exemplo = store.obter("pergunta_exemplo")
    store.definir("pergunta_exemplo", None)
    if pergunta_exemplo and not indisponivel:
        pergunta = pergunta_exemplo
    if pergunta:
        store.adicionar_mensagem(contexto, {"role": "user", "content": pergunta})
        with st.chat_message("user"):
            st.write(pergunta)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.info("▰ ▰ ▰ Buscando fontes e redigindo a resposta…")
            with st.spinner("Conferindo as fontes…"):
                resposta = dados.perguntar(pergunta, historico, filtros["servico"])
            placeholder.empty()
            if resposta.get("abstained") or resposta.get("blocked"):
                st.warning("Não foi possível fundamentar uma orientação para esta pergunta. Confirme com a equipe responsável pelo serviço.")
            st.write(resposta.get("answer", "Sem resposta disponível."))
            _fontes(resposta.get("citations", []))
        store.adicionar_mensagem(contexto, {"role": "assistant", "content": resposta.get("answer", ""),
                                           "citations": resposta.get("citations", [])})
