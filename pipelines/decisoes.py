"""Auditoria local e rascunhos: nada é enviado automaticamente."""
from datetime import datetime, timezone
import json
from pathlib import Path

from providers.config import carregar

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
    with arquivo.open("a", encoding="utf-8") as saida:
        saida.write(json.dumps(registro, ensure_ascii=False, allow_nan=False) + "\n")
    return registro


def ja_decidida(id, caminho=None):
    return any(registro["id"] == id for registro in listar(caminho))


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
                orientacao = resposta["answer"].strip()
        except Exception:
            pass  # Indisponibilidade do RAG mantém o rascunho local utilizável.
    return inicio + orientacao + "\nO atendimento não garante concessão nem pagamento do benefício."


if __name__ == "__main__":
    try:
        print(f"{len(listar())} decisões registradas. Nenhuma mensagem enviada.")
    except ValueError as erro:
        print(erro)
