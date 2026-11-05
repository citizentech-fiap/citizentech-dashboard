"""Agregações de pedidos; listas de documentos usam tokens exatos."""
from collections import Counter
import argparse

import pandas as pd

from providers.rpa import pedidos as ler_pedidos
from providers.config import carregar


def documentos(valor):
    if isinstance(valor, (list, tuple, set)):
        return {str(item).strip() for item in valor if str(item).strip()}
    if pd.isna(valor):
        return set()
    return {item.strip() for item in str(valor).split(";") if item.strip()}


def resumo(pedidos):
    """Uma linha por município; chamador deve filtrar o ano antes de agregar.

    familias_garantia_safra conta solicitações de GS, aproximação sintética de
    famílias inscritas (não confirma inscrição oficial nem identifica pessoas).
    docs_completos exclui revisão humana, inválidos e documentos ilegíveis.
    """
    colunas = ["cod_ibge", "municipio", "uf", "pedidos", "familias_garantia_safra",
               "travados_sem_caf", "docs_mais_faltantes", "revisao_humana", "docs_completos"]
    linhas = []
    for codigo, grupo in pedidos.groupby("cod_ibge", dropna=True):
        faltantes = grupo.docs_faltantes.map(documentos)
        ilegiveis = grupo.docs_ilegiveis.map(documentos)
        contagem = Counter(doc for lista in faltantes for doc in lista)
        completos = faltantes.map(len).eq(0) & ilegiveis.map(len).eq(0) & grupo.decisao.eq("resolvido")
        linhas.append({"cod_ibge": int(codigo), "municipio": grupo.municipio.iloc[0],
                       "uf": grupo.uf.iloc[0], "pedidos": len(grupo),
                       "familias_garantia_safra": int(grupo.service_id.eq("garantia_safra").sum()),
                       "travados_sem_caf": int((grupo.service_id.isin(["garantia_safra", "pronaf"]) &
                                                faltantes.map(lambda docs: "caf" in docs)).sum()),
                       "docs_mais_faltantes": dict(sorted(contagem.items(), key=lambda x: (-x[1], x[0]))),
                       "revisao_humana": int(grupo.decisao.eq("revisao_humana").sum()),
                       "docs_completos": int(completos.sum())})
    return pd.DataFrame(linhas, columns=colunas)


def por_servico(pedidos):
    return pedidos.groupby(["cod_ibge", "municipio", "uf", "service_id"]).size().reset_index(name="pedidos")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=carregar()["safra"]["ano_padrao"])
    args = parser.parse_args()
    try:
        todos = ler_pedidos()
        print(f"Demanda sintética/viva — safra {args.ano}")
        print(resumo(todos.loc[todos.ano == args.ano]).to_string(index=False))
    except (FileNotFoundError, ValueError) as erro:
        print(f"Pedidos indisponíveis: {erro}")
