"""Integração opcional; nunca carrega arquivos .env."""
from importlib import import_module
import sys
from unittest.mock import patch

from providers.config import carregar


def criar_rag():
    """Retorna (assistente, motivo); falhas e índice indisponível são recuperáveis.

    O citizen_rag local chama load_env() ao criar o LLM. Desabilitamos apenas
    essa carga durante a construção; credenciais já no ambiente seguem válidas.
    """
    try:
        cfg = carregar()
        try:
            modulo = import_module("citizen_rag.rag")
        except ModuleNotFoundError as erro:
            if erro.name not in ("citizen_rag", "citizen_rag.rag"):
                raise
            pasta = cfg["paths"]["genai_path"]
            if not (pasta / "citizen_rag").is_dir():
                return None, f"Pacote citizen_rag ausente em {pasta}."
            sys.path.insert(0, str(pasta))
            try:
                modulo = import_module("citizen_rag.rag")
            finally:
                sys.path.remove(str(pasta))
        configuracao = import_module("citizen_rag.config")
        cache_rag = cfg["paths"]["cache_http"] / "rag"
        with patch.object(configuracao, "load_env", lambda: None, create=True):
            rag = modulo.RAGAssistant(overrides={"paths": {
                "index_dir": str(cache_rag / "indexes"),
                "llm_cache_dir": str(cache_rag / "llm"),
                "log_file": str(cache_rag / "rag.log"),
            }})
        if getattr(rag, "_init_error", None):
            return None, f"Índice RAG indisponível: {rag._init_error}"
        return rag, "RAG disponível; respostas sem evidência usam o template local."
    except Exception as erro:
        return None, f"RAG indisponível ({type(erro).__name__}); usando template local."
