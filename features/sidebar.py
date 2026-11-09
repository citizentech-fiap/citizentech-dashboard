"""Conecta os comandos da barra lateral à camada de estado."""
from state import dados
from ui.sidebar import renderizar as painel

def renderizar(cfg, municipios):
    painel(cfg, municipios, dados.atualizar_municipio)
