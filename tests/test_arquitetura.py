"""Contratos de imports; state.store é permitido na UI para estado de widgets."""
import ast
from pathlib import Path
import unittest

RAIZ = Path(__file__).resolve().parents[1]
REGRAS = {
    "providers": {"streamlit", "state", "ui", "features", "scripts"},
    "pipelines": {"streamlit", "state", "ui", "features", "scripts"},
    "ui": {"providers", "pipelines", "scripts", "state.dados"},
    "features": {"providers", "scripts"},
    "state": {"scripts"},
}


class TestArquitetura(unittest.TestCase):
    def test_imports_respeitam_camadas(self):
        for camada, proibidos in REGRAS.items():
            for arquivo in (RAIZ / camada).rglob("*.py"):
                arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
                for no in ast.walk(arvore):
                    nomes = []
                    if isinstance(no, ast.Import):
                        nomes = [a.name for a in no.names]
                    elif isinstance(no, ast.ImportFrom):
                        modulo = no.module or ""
                        if no.level:
                            pacote = arquivo.relative_to(RAIZ).parts[:-1]
                            base = pacote[:len(pacote)-no.level+1]
                            modulo = ".".join((*base, modulo)).rstrip(".")
                        nomes = [modulo, *[f"{modulo}.{a.name}" for a in no.names]]
                    for nome in nomes:
                        with self.subTest(arquivo=str(arquivo), importacao=nome):
                            self.assertFalse(any(nome == p or nome.startswith(p + ".") for p in proibidos))
