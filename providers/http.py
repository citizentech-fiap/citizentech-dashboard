"""GET resiliente com cache de bytes descomprimidos, sem dependência da UI."""
import gzip
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
from pathlib import Path
import tempfile
import time

import requests

from providers.config import carregar

USER_AGENT = "CitizenTechBot/1.0 (projeto academico FIAP)"


def gravar_atomico(caminho, conteudo: bytes):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(dir=caminho.parent, suffix=".tmp")
    try:
        with os.fdopen(descritor, "wb") as saida:
            saida.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def get(url, params=None, *, cache=True, forcar=False, cfg=None) -> bytes:
    """Retorna bytes; retries é o número de novas tentativas após a primeira.

    Requests normalmente descomprime gzip; a assinatura cobre também servidores
    que devolvem gzip sem Content-Encoding. Cache não expira: são snapshots
    históricos, renovados explicitamente com forcar=True.
    """
    cfg = cfg or carregar()
    fontes = cfg["fontes"]
    endereco = requests.Request("GET", url, params=params).prepare().url
    chave = hashlib.sha256(endereco.encode()).hexdigest()
    arquivo = Path(cfg["paths"]["cache_http"]) / f"{chave}.bin"
    if cache and not forcar and arquivo.exists():
        return arquivo.read_bytes()
    for tentativa in range(fontes["retries"] + 1):
        try:
            resposta = requests.get(
                endereco, timeout=fontes["timeout_s"],
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
            )
            resposta.raise_for_status()
            conteudo = resposta.content
            if conteudo.startswith(b"\x1f\x8b"):
                conteudo = gzip.decompress(conteudo)
            if cache:
                gravar_atomico(arquivo, conteudo)
            return conteudo
        except requests.RequestException as erro:
            status = getattr(getattr(erro, "response", None), "status_code", None)
            transitorio = status is None or status == 429 or 500 <= status <= 599
            if not transitorio or tentativa == fontes["retries"]:
                raise requests.RequestException(
                    f"Falha no GET {endereco}: {erro}", response=getattr(erro, "response", None)
                ) from erro
            espera = fontes["backoff_s"] * 2 ** tentativa
            # Respeita o prazo do servidor se houver (segundos ou data HTTP).
            resposta_erro = getattr(erro, "response", None)
            prazo = resposta_erro.headers.get("Retry-After") if resposta_erro is not None else None
            if isinstance(prazo, str):
                try:
                    espera = max(espera, float(prazo))
                except ValueError:
                    try:
                        espera = max(espera, (parsedate_to_datetime(prazo) -
                                             datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError):
                        pass
            time.sleep(espera)
