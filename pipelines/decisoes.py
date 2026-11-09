"""Auditoria local e rascunhos: nada é enviado automaticamente."""
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
import json
import re
from pathlib import Path

from providers.config import carregar
from providers.http import gravar_atomico

CAMPOS = {"id", "tipo", "municipio", "decisao", "justificativa", "mensagem", "quando", "usuario"}


def _arquivo(caminho):
    return Path(caminho) if caminho else carregar()["paths"]["decisoes"]


def listar(caminho=None):
    arquivo = _arquivo(caminho)
    if not arquivo.exists():
        return []
    registros = []
    for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if linha.strip():
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError as erro:
                raise ValueError(f"Registro de decisões inválido na linha {numero}: {arquivo}") from erro
    return registros


def registrar(decisao, caminho=None):
    registro = dict(decisao)
    registro.setdefault("quando", datetime.now(timezone.utc).isoformat())
    if set(registro) != CAMPOS:
        raise ValueError(f"Decisão deve conter os campos {sorted(CAMPOS)}.")
    if registro["decisao"] not in ("aprovada", "editada", "rejeitada"):
        raise ValueError("Decisão deve ser aprovada, editada ou rejeitada.")
    if registro["tipo"] not in ("vistoria", "mutirao_caf", "convocacao"):
        raise ValueError("Tipo de recomendação inválido.")
    if not all(isinstance(v, str) for v in registro.values()):
        raise ValueError("Campos da decisão devem ser textos.")
    if not all(registro[c].strip() for c in ("id", "municipio", "usuario", "quando")):
        raise ValueError("Identificação da decisão, município, usuário e data são obrigatórios.")
    datetime.fromisoformat(registro["quando"])
    arquivo = _arquivo(caminho)
    # Valida o histórico antes de acrescentar; não sobrescreve decisões anteriores.
    listar(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    anterior = arquivo.read_bytes() if arquivo.exists() else b""
    gravar_atomico(arquivo, anterior + (json.dumps(registro, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
    return registro


def ja_decidida(id, caminho=None):
    return any(registro["id"] == id for registro in listar(caminho))


def texto_para_agricultor(resposta):
    """A resposta do RAG vem em Markdown e com citações [n] — úteis na tela, sem sentido numa mensagem
    ao agricultor. Remove marcações (**negrito**, títulos) e números de citação, preservando links."""
    texto = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", resposta)
    texto = re.sub(r"\*\*|__|^#+\s*", "", texto, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def rascunho_convocacao(rec, rag=None):
    inicio = (f"Convocação para atendimento — {rec.municipio}\n"
              f"{rec.titulo}.\nData, horário e local: a confirmar pelo gestor.\n")
    orientacao = ("Leve documento de identidade, CPF e os comprovantes exigidos pelo serviço solicitado. "
                  "Para Garantia-Safra ou Pronaf, leve o comprovante de inscrição no CAF. "
                  "Confirme a relação de documentos com a equipe municipal antes do atendimento.")
    if rag is not None:
        try:
            resposta = rag.answer(
                "O que o agricultor deve levar e fazer no atendimento para Garantia-Safra?",
                service_id="garantia_safra")
            if (not resposta.get("abstained", True) and not resposta.get("blocked", False)
                    and resposta.get("answer", "").strip()):
                orientacao = texto_para_agricultor(resposta["answer"])
        except Exception:
            pass  # Indisponibilidade do RAG mantém o rascunho local utilizável.
    return inicio + orientacao + "\nO atendimento não garante concessão nem pagamento do benefício."


def salvar_decisao(rec, escolha, justificativa, mensagem, usuario, cfg=None):
    """Só chamado após a revisão humana. Sem envio, destinatário ou dado pessoal."""
    cfg = cfg or carregar()
    if escolha == "rejeitada" and not justificativa.strip():
        raise ValueError("Explique o motivo da rejeição.")
    if not usuario.strip():
        raise ValueError("Informe a identificação funcional do gestor.")
    if ja_decidida(rec.id, cfg["paths"]["decisoes"]):
        raise ValueError("Esta recomendação já foi decidida. Consulte o histórico.")
    if escolha not in ("aprovada", "editada", "rejeitada"):
        raise ValueError("Decisão inválida.")
    registro = dict(id=rec.id, tipo=rec.tipo, municipio=rec.municipio, decisao=escolha,
                    justificativa=justificativa.strip(), mensagem=mensagem.strip(), usuario=usuario.strip())
    arquivo = None
    if escolha != "rejeitada" and rec.tipo in ("convocacao", "mutirao_caf"):
        if not mensagem.strip():
            raise ValueError("Revise e preencha a mensagem antes de confirmar.")
        arquivo = cfg["paths"]["convocacoes"] / f"{rec.id}.eml"
        if arquivo.exists():
            raise ValueError("Já existe uma mensagem para esta recomendação. Verifique o histórico local.")
        eml = EmailMessage(policy=SMTP)
        eml["Subject"] = f"Mandacaru | {rec.titulo}"
        eml["Date"] = datetime.now(timezone.utc)
        eml["X-Unsent"] = "1"
        eml.set_content(mensagem.strip())
        gravar_atomico(arquivo, eml.as_bytes())
    try:
        return registrar(registro, cfg["paths"]["decisoes"])
    except Exception:
        if arquivo is not None:
            arquivo.unlink(missing_ok=True)
        raise


def selos(historico):
    """Última decisão por ID, com autoria e data para cartões e mapa."""
    return {r["id"]: dict(r) for r in historico}


if __name__ == "__main__":
    try:
        print(f"{len(listar())} decisões registradas. Nenhuma mensagem enviada.")
    except ValueError as erro:
        print(erro)
