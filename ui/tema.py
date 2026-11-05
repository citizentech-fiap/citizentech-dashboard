"""Tokens visuais e uma única escala semântica para todo o painel."""
from html import escape

import streamlit as st

CORES = {
    "fundo": "#FAF8F2", "superficie": "#FFFFFF", "texto": "#202923",
    "muted": "#57635A", "primaria": "#176449", "borda": "#DDDCD2",
    "seguro": "#176449", "atencao": "#806000", "alerta": "#A5430A", "critico": "#AF2430",
}
RISCOS = {
    "seguro": ("✓", "Seguro"), "atencao": ("◐", "Atenção"),
    "alerta": ("▲", "Alerta"), "critico": ("!", "Crítico"),
}
ESPACOS = {"pequeno": "0.5rem", "medio": "1rem", "grande": "1.5rem"}
RAIOS = {"card": "14px", "badge": "30px"}


def aplicar():
    st.html(f"""<style>
    .stApp {{ background: {CORES['fundo']}; color: {CORES['texto']}; }}
    .block-container {{ max-width: 1440px; padding-top: 2rem; }}
    h1,h2,h3 {{ letter-spacing: -0.035em; }}
    h1 {{ font-size: 2.25rem !important; }}
    h2 {{ font-size: 1.5rem !important; }}
    h3 {{ font-size: 1.15rem !important; }}
    [data-testid="stSidebar"] {{ border-right: 1px solid {CORES['borda']}; }}
    [data-testid="stMetric"] {{ background: {CORES['superficie']}; border: 1px solid {CORES['borda']};
      padding: {ESPACOS['medio']}; border-radius: {RAIOS['card']}; }}
    [data-testid="stVerticalBlockBorderWrapper"] > div {{ border-radius: {RAIOS['card']}; }}
    .mandacaru-kpi {{ background: {CORES['superficie']}; border: 1px solid {CORES['borda']};
      border-top: 4px solid var(--cor); padding: {ESPACOS['medio']}; border-radius: {RAIOS['card']}; min-height: 130px; }}
    .mandacaru-kpi .rotulo {{ color: {CORES['muted']}; font-size: .85rem; }}
    .mandacaru-kpi .valor {{ color: var(--cor); font-weight: 750; font-size: 2rem; line-height: 1.4; }}
    .mandacaru-kpi .detalhe {{ color: {CORES['muted']}; font-size: .8rem; }}
    .badge {{ color: var(--cor); border: 1px solid var(--cor); border-radius: {RAIOS['badge']};
      padding: .2rem .65rem; font-size: .8rem; font-weight: 650; display: inline-block; background: white; }}
    .legenda {{ display: flex; flex-wrap: wrap; gap: {ESPACOS['pequeno']}; margin: .7rem 0 1.1rem; }}
    .sobretitulo {{ color: {CORES['primaria']}; letter-spacing: .13em; font-size: .72rem; font-weight: 750; text-transform: uppercase; }}
    .resumo {{ font-size: 1.15rem; line-height: 1.55; max-width: 75ch; margin: .3rem 0 1rem; }}
    button, input, textarea {{ font-family: inherit; }}
    @media(max-width: 700px) {{ .block-container {{ padding-top: 1rem; }} h1 {{font-size: 1.8rem !important;}} }}
    </style>""")


def badge_html(classe, complemento=""):
    icone, rotulo = RISCOS[classe]
    return f'<span class="badge" style="--cor:{CORES[classe]}">{icone} {rotulo}{escape(complemento)}</span>'


def escala_risco(cfg):
    """Degraus nos mesmos limites inclusivos usados pelo pipeline."""
    classes = sorted(cfg["risco"]["classes"].items(), key=lambda item: item[1])
    escala = []
    for indice, (classe, minimo) in enumerate(classes):
        fim = classes[indice + 1][1] if indice + 1 < len(classes) else 100
        escala.extend([(minimo / 100, CORES[classe]), (fim / 100, CORES[classe])])
    return escala


def legenda(cfg):
    classes = sorted(cfg["risco"]["classes"].items(), key=lambda item: item[1])
    itens = []
    for i, (classe, minimo) in enumerate(classes):
        faixa = f" · {minimo}–<{classes[i+1][1]}%" if i + 1 < len(classes) else f" · {minimo}–100%"
        itens.append(badge_html(classe, faixa))
    st.html('<div class="legenda" aria-label="Classes de perda estimada">' + "".join(itens) + "</div>")


# Rótulos de exibição (os códigos vêm do robô de RPA; ver ../RPA/config.yaml).
NOMES_SERVICOS = {
    "garantia_safra": "Garantia-Safra", "caf": "CAF", "pronaf": "Pronaf",
    "aposentadoria_rural": "Aposentadoria rural", "salario_maternidade_rural": "Salário-maternidade rural",
    "cadunico": "Cadastro Único", "bolsa_familia": "Bolsa Família", "bpc": "BPC", "cpf": "CPF",
}
NOMES_DOCUMENTOS = {
    "documento_identidade": "Identidade com foto", "cpf": "CPF", "comprovante_residencia": "Comprovante de residência",
    "certidao_civil": "Certidão civil", "comprovante_renda": "Comprovante de renda",
    "caf": "Comprovante do CAF", "comprovante_posse_terra": "Posse da terra",
}
