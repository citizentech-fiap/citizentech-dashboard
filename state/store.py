"""Única porta para o estado da sessão, inclusive callbacks de widgets."""
from copy import deepcopy

import streamlit as st

ABAS = ("Panorama da seca", "Raio-x do município", "Mesa de decisão", "Assistente")


def obter(chave, padrao=None):
    return st.session_state.get(chave, padrao)


def definir(chave, valor):
    st.session_state[chave] = valor


def iniciar(cfg, ufs):
    defaults = {
        "ufs": list(ufs), "ano": cfg["safra"]["ano_demo_seca"],
        "cultura": cfg["modelo_hidrico"]["cultura_padrao"],
        "limiar": cfg["risco"]["criterio_garantia_safra"], "servico": "todos",
        "mes": int(cfg["safra"]["fim_mes_dia"][:2]), "aba": ABAS[0],
        "municipio": None, "rascunhos": {}, "conversas": {}, "rag_ativado": False,
        "aviso_atualizacao": None, "notificacao": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            definir(chave, deepcopy(valor))
    # Mantém as escolhas das abas com renderização condicional entre reruns.
    for chave in defaults:
        definir(chave, obter(chave))


def filtros():
    return {k: obter(k) for k in ("ufs", "ano", "cultura", "limiar", "servico")}


def abrir_municipio(codigo):
    definir("municipio", int(codigo))
    definir("aba", ABAS[1])


def selecionar_municipio():
    definir("municipio", obter("_municipio"))


def guardar_rascunho(id_rec, valor):
    rascunhos = dict(obter("rascunhos", {}))
    if valor is None:
        rascunhos.pop(id_rec, None)
    else:
        rascunhos[id_rec] = valor
    definir("rascunhos", rascunhos)


def adicionar_mensagem(contexto, mensagem):
    conversas = deepcopy(obter("conversas", {}))
    conversas.setdefault(contexto, []).append(mensagem)
    definir("conversas", conversas)


def consumir_notificacao():
    aviso = obter("notificacao")
    definir("notificacao", None)
    return aviso
