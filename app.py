"""Mandacaru: entrada fina, filtros compartilhados e jornada de decisão."""
import streamlit as st

from features import assistente, decisoes, municipio, panorama
from providers.config import carregar
from state import dados, store
from ui import tema
from ui.componentes import aviso_modelo, fontes
from ui.sidebar import renderizar as sidebar


def principal():
    cfg = carregar()
    st.set_page_config(page_title="Mandacaru · onde agir primeiro", page_icon="🌵", layout="wide")
    tema.aplicar()
    versao = dados.versao_snapshots()
    try:
        with st.spinner("Abrindo os snapshots do território…"):
            municipios, malhas, aviso_mapa = dados.catalogos(versao)
    except (OSError, ValueError):
        st.error("Não foi possível abrir o catálogo de municípios. Recupere os snapshots com scripts/preparar_dados.py e recarregue a página.")
        return
    store.iniciar(cfg, sorted(municipios.uf.unique()))
    sidebar(cfg, municipios)
    filtros = store.filtros()
    filtros["ufs"] = tuple(filtros["ufs"])
    st.html('<div class="sobretitulo">Mandacaru / Garantia-Safra + EMATER</div>')
    st.title("Onde agir primeiro, e como?")
    if filtros["ano"] == cfg["safra"]["ano_demo_seca"]:
        st.caption(f"Modo demonstração: seca de {cfg['safra']['ano_demo_seca']}. A safra {cfg['safra']['ano_padrao']} está dentro da normal — troque o ano na barra lateral.")
    if not filtros["ufs"]:
        st.info("Escolha ao menos uma UF na barra lateral para começar.")
        return
    try:
        with st.spinner("Calculando indicadores e prioridades da safra…"):
            ctx = dados.contexto(**filtros, versao=versao)
    except (OSError, ValueError) as erro:
        st.warning(f"Não foi possível calcular esta safra com os snapshots disponíveis. {erro}")
        st.info("Selecione outro ano ou recupere os dados com scripts/preparar_dados.py. Nenhuma chuva ausente é tratada como zero.")
        return
    quadro = ctx["quadro"]
    if quadro.empty:
        st.info("Não há municípios neste recorte. Amplie as UFs selecionadas.")
        return
    quantidade = int(quadro.perda_estimada_pct.ge(filtros["limiar"]).sum())
    st.write(f"**Safra {filtros['ano']}: {quantidade} de {len(quadro)} municípios com perda estimada no limiar de {filtros['limiar']}% ou acima.** "
             f"{int(quadro.travados_sem_caf.sum())} pedidos travados sem CAF no recorte.")
    aviso_modelo()
    tema.legenda(cfg)
    for aviso in (ctx["aviso"], aviso_mapa):
        if aviso:
            st.warning(aviso)
    notificacao = store.consumir_notificacao()
    if notificacao:
        st.success(notificacao)
    abas = st.tabs(store.ABAS, key="aba", on_change="rerun")
    for indice, aba in enumerate(abas):
        if aba.open:
            with aba:
                if indice == 0:
                    panorama.renderizar(ctx, cfg, filtros, versao, malhas)
                elif indice == 1:
                    municipio.renderizar(ctx, cfg, filtros, versao)
                elif indice == 2:
                    decisoes.renderizar(ctx, cfg, filtros)
                else:
                    assistente.renderizar(ctx, cfg, filtros)
    st.divider()
    fontes()


if __name__ == "__main__":
    principal()
