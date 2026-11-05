"""Guarda contra texto corrompido por codificação (ex.: "a??es" no lugar de "ações").

Já aconteceu: um arquivo regravado pelo PowerShell em ANSI perdeu os acentos de toda a interface.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXTENSOES = {".py", ".md", ".yaml", ".toml", ".svg", ".csv"}
PASTAS_IGNORADAS = {".git", "__pycache__", "output", "cache_http", ".venv"}
URL = re.compile(r"https?://\S+")


def arquivos():
    for caminho in RAIZ.rglob("*"):
        if caminho == Path(__file__).resolve():  # este arquivo cita os padrões de propósito
            continue
        if caminho.is_file() and caminho.suffix in EXTENSOES and not PASTAS_IGNORADAS & set(caminho.parts):
            yield caminho


class TestCodificacao(unittest.TestCase):
    def test_arquivos_em_utf8_sem_acentos_perdidos(self):
        problemas = []
        for caminho in arquivos():
            try:
                texto = caminho.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                problemas.append(f"{caminho.relative_to(RAIZ)}: não é UTF-8")
                continue
            if "�" in texto:
                problemas.append(f"{caminho.relative_to(RAIZ)}: contém caractere de substituição �")
            for n, linha in enumerate(texto.splitlines(), 1):
                if re.search(r"[A-Za-zÀ-ú]\?{1,2}[a-zà-ú]", URL.sub("", linha)):
                    problemas.append(f"{caminho.relative_to(RAIZ)}:{n}: {linha.strip()[:80]}")
        self.assertEqual(problemas, [], "Texto com codificação corrompida:\n" + "\n".join(problemas))


if __name__ == "__main__":
    unittest.main()
