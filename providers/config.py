"""Configuração única; caminhos independentes do diretório de execução."""
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]


def carregar(arquivo=None) -> dict:
    caminho = Path(arquivo) if arquivo else RAIZ / "config.yaml"
    with caminho.open(encoding="utf-8") as entrada:
        cfg = yaml.safe_load(entrada)
    if not isinstance(cfg, dict) or "paths" not in cfg:
        raise ValueError(f"Configuração inválida: {caminho}")
    cfg["paths"] = {chave: (RAIZ / valor).resolve()
                    for chave, valor in cfg["paths"].items()}
    return cfg
