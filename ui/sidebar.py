"""Filtros globais e atualização explícita da fonte climática."""
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from state import dados, store
from ui.tema import NOMES_SERVICOS


def atualizar(municipios, ano):
    solicitacao = uuid4().hex
    falhas, sucessos = [], []
    progresso = st.progress(0, text="Consultando o Open-Meteo…")
    with st.status("Atualizando município a município", expanded=True) as status:
        for indice, m in enumerate(municipios.itertuples(index=False), 1):
            progresso.progress((indice - 1) / len(municipios), text=f"Atualizando {m.municipio}…")
            try:
                dados.atualizar_municipio(int(m.cod_ibge), ano, solicitacao)
                sucessos.append(m.municipio)
            except Exception:
                # A preparação mantém o último snapshot íntegro em falhas de rede.
                falhas.append(m.municipio)
            progresso.progress(indice / len(municipios), text=f"{indice}/{len(municipios)} municípios verificados")
        status.update(label="Atualização concluída" if not falhas else "Atualização com dados locais preservados",
                      state="complete" if not falhas else "error", expanded=False)
    store.definir("aviso_atualizacao", {"sucessos": sucessos, "falhas": falhas,
                   "quando": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")})
    st.rerun()


def renderizar(cfg, municipios):
    with st.sidebar:
        st.image(str(cfg["paths"]["municipios"].parents[1] / "assets/logo.svg"), width=48)
        st.markdown("### Mandacaru")
        st.selectbox("Safra", cfg["safra"]["anos_disponiveis"], key="ano",
                     format_func=lambda a: f"{a} — seca histórica" if a == cfg["safra"]["ano_demo_seca"] else str(a))
        st.multiselect("Estados", sorted(municipios.uf.unique()), key="ufs", help="Filtros válidos nas quatro abas.")
        with st.expander("Ajustes avançados"):
            culturas = cfg["modelo_hidrico"]["culturas"]
            st.selectbox("Cultura", list(culturas), key="cultura", format_func=lambda c: culturas[c]["nome"])
            st.slider("Limiar de alerta (%)", cfg["interface"]["limiar_min"], cfg["interface"]["limiar_max"],
                      step=cfg["interface"]["limiar_passo"], key="limiar",
                      help="Explora prioridades; não muda as classes de risco nem aprova benefício.")
            servicos = ["todos", *cfg["simulacao"]["pesos_servicos"]]
            st.selectbox("Serviço", servicos, key="servico",
                         format_func=lambda s: "Todos os serviços" if s == "todos" else NOMES_SERVICOS.get(s, s))
            st.caption("Fonte dos pedidos: " + ("demonstração sintética, sem dados pessoais." if cfg["fontes"]["pedidos"] == "snapshot" else "planilha do robô de triagem."))
            if st.button("Atualizar dados do Open-Meteo", disabled=not store.obter("ufs"), width="stretch",
                         help="Renova a safra dos estados escolhidos. Pode levar alguns minutos. Preserva a normal 1991–2020."):
                atualizar(municipios.loc[municipios.uf.isin(store.obter("ufs"))], store.obter("ano"))
            relatorio = store.obter("aviso_atualizacao")
            if relatorio:
                st.caption(f"{relatorio['quando']} · {len(relatorio['sucessos'])} atualizados.")
                if relatorio["falhas"]:
                    st.warning("API indisponível para " + ", ".join(relatorio["falhas"]) + ". Usando os últimos dados locais; tente novamente mais tarde.")
