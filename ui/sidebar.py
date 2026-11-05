"""Filtros globais e atualização explícita da fonte climática."""
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from state import dados, store


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
        status.update(label="Atualização concluída" if not falhas else "Atualização com snapshot preservado",
                      state="complete" if not falhas else "error", expanded=False)
    store.definir("aviso_atualizacao", {"sucessos": sucessos, "falhas": falhas,
                   "quando": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")})
    st.rerun()


def renderizar(cfg, municipios):
    with st.sidebar:
        st.image(str(cfg["paths"]["municipios"].parents[1] / "assets/logo.svg"), width=48)
        st.markdown("### Mandacaru")
        st.caption("Decidir hoje. Proteger a próxima safra.")
        st.divider()
        st.markdown("**Seu território, sua safra**")
        st.multiselect("UF", sorted(municipios.uf.unique()), key="ufs")
        st.selectbox("Safra / ano", cfg["safra"]["anos_disponiveis"], key="ano",
                     format_func=lambda a: f"{a} — grande seca" if a == cfg["safra"]["ano_demo_seca"] else str(a))
        culturas = cfg["modelo_hidrico"]["culturas"]
        st.selectbox("Cultura", list(culturas), key="cultura", format_func=lambda c: culturas[c]["nome"])
        st.slider("Limiar de alerta (%)", cfg["interface"]["limiar_min"], cfg["interface"]["limiar_max"],
                  step=cfg["interface"]["limiar_passo"], key="limiar")
        st.caption(f"{cfg['risco']['criterio_garantia_safra']}% é a referência oficial. Ajustar o limiar explora prioridades; não muda as classes de risco nem aprova benefício.")
        st.caption("Vistorias e convocações preservam as regras mínimas do modelo. Mutirões de CAF dependem das pendências, mesmo sem seca.")
        servicos = ["todos", *cfg["simulacao"]["pesos_servicos"]]
        st.selectbox("Serviço (demanda)", servicos, key="servico",
                     format_func=lambda s: "Todos os serviços" if s == "todos" else s.replace("_", " ").capitalize())
        st.caption("Filtros válidos nas quatro abas. O mês de replay vale apenas no panorama.")
        st.divider()
        with st.expander("Dados e atualização"):
            st.caption("A abertura usa snapshots locais. Este botão renova a safra selecionada para as UFs escolhidas; pode levar alguns minutos. A normal 1991–2020 é preservada.")
            if st.button("Atualizar dados do Open-Meteo", disabled=not store.obter("ufs"), width="stretch"):
                atualizar(municipios.loc[municipios.uf.isin(store.obter("ufs"))], store.obter("ano"))
            relatorio = store.obter("aviso_atualizacao")
            if relatorio:
                st.caption(f"{relatorio['quando']} · {len(relatorio['sucessos'])} atualizados.")
                if relatorio["falhas"]:
                    st.warning("API indisponível para " + ", ".join(relatorio["falhas"]) + ". Usando o último snapshot local; tente novamente mais tarde.")
