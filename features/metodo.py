"""Prepara a validação selecionada antes de compor a interface."""
from pipelines.realidade import recortar_validacao
from state import dados
from ui.componentes import como_calculamos as componente


def como_calculamos(cfg, filtros):
    try:
        placar = dados.validacao(filtros["cultura"], dados.versao_snapshots())
        placar = recortar_validacao(placar, cfg, filtros)
    except (OSError, ValueError):
        placar = None
    componente(cfg, filtros, placar)
