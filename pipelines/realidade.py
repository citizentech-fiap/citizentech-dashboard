"""Validação retrospectiva com PAM e pagamentos; nunca alimenta recomendações."""
import json

import numpy as np
import pandas as pd

from pipelines import risco
from providers import dados_locais
from providers.config import carregar


def perda_real(cultura, dados=None):
    """Exige os dez anos anteriores completos e válidos; não preenche ausências."""
    cfg = carregar()
    if cultura not in cfg["modelo_hidrico"]["culturas"]:
        raise ValueError(f"Cultura desconhecida: {cultura}")
    dados = dados_locais.pam() if dados is None else dados.copy()
    dados = dados.loc[dados.cultura.eq(cultura)].sort_values(["cod_ibge", "ano"]).copy()
    if dados.duplicated(["cod_ibge", "ano"]).any():
        raise ValueError("PAM duplicada por município/ano/cultura.")
    janela = cfg["realidade"]["anos_media"]
    resultados = []
    for _, grupo in dados.groupby("cod_ibge"):
        serie = grupo.set_index("ano").producao_t
        medias = [serie.reindex(range(ano - janela, ano)).mean()
                  if serie.reindex(range(ano - janela, ano)).notna().all() else np.nan
                  for ano in grupo.ano]
        grupo = grupo.assign(producao_media_10_anos_t=medias)
        grupo["perda_producao_pct"] = ((1 - grupo.producao_t /
                                         grupo.producao_media_10_anos_t.where(
                                             grupo.producao_media_10_anos_t.gt(0))) * 100).clip(0, 100)
        grupo["perda_area_pct"] = ((1 - grupo.area_colhida_ha /
                                    grupo.area_plantada_ha.where(grupo.area_plantada_ha.gt(0))) * 100).clip(0, 100)
        resultados.append(grupo)
    return pd.concat(resultados, ignore_index=True) if resultados else dados.assign(
        producao_media_10_anos_t=np.nan, perda_producao_pct=np.nan, perda_area_pct=np.nan)


def pagamentos():
    return dados_locais.garantia_safra()


def _cobertura_pagamentos(ano, cfg):
    arquivo = cfg["paths"]["garantia_safra_cobertura"]
    cobertura = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    meses = pd.period_range(f"{ano}-07", f"{ano + 1}-06", freq="M")
    return all(cobertura.get(m.strftime("%Y%m")) == "disponivel" for m in meses)


def validacao(cultura):
    """Matriz: linhas estimado <40/≥40, colunas real <40/≥40; só pares válidos.

    Spearman = Pearson dos postos médios, sem dependência adicional do SciPy.
    Pagamento é contexto retrospectivo, não verdade-terreno da classificação.
    """
    cfg = carregar()
    anos = [a for a in cfg["safra"]["anos_disponiveis"] if a <= cfg["fontes"]["pam_fim"]]
    estimativas = pd.concat([risco.indicadores(a, cultura).assign(ano=a) for a in anos], ignore_index=True)
    reais = perda_real(cultura)
    base = estimativas.merge(reais[["cod_ibge", "ano", "perda_producao_pct", "perda_area_pct"]],
                             on=["cod_ibge", "ano"], how="left", validate="one_to_one")
    avisos = []
    try:
        pagos = pagamentos().rename(columns={"safra": "ano"})
    except (FileNotFoundError, ValueError) as erro:
        pagos = pd.DataFrame(columns=["cod_ibge", "ano", "familias", "valor_total", "meses_com_pagamento"])
        avisos.append(str(erro))
    base = base.merge(pagos[["cod_ibge", "ano", "familias", "valor_total", "meses_com_pagamento"]],
                      on=["cod_ibge", "ano"], how="left", validate="one_to_one")
    cobertura = {ano: _cobertura_pagamentos(ano, cfg) for ano in anos}
    base["cobertura_pagamentos_completa"] = base.ano.map(cobertura)
    base["pagou_garantia_safra"] = pd.array([
        True if pd.notna(f) and f > 0 else (False if completo else pd.NA)
        for f, completo in zip(base.familias, base.cobertura_pagamentos_completa)], dtype="boolean")
    # Apenas ausência em cobertura completa pode ser interpretada como zero.
    for coluna in ("familias", "valor_total", "meses_com_pagamento"):
        base.loc[base.cobertura_pagamentos_completa, coluna] = base.loc[
            base.cobertura_pagamentos_completa, coluna].fillna(0)
    pares = base.dropna(subset=["perda_estimada_pct", "perda_producao_pct"]).copy()
    criterio = cfg["risco"]["criterio_garantia_safra"]
    estimado, real = pares.perda_estimada_pct.ge(criterio), pares.perda_producao_pct.ge(criterio)
    matriz = pd.crosstab(estimado, real).reindex(index=[False, True], columns=[False, True], fill_value=0)
    matriz.index.name, matriz.columns.name = "estimado_ge_40", "real_ge_40"
    postos = pares[["perda_estimada_pct", "perda_producao_pct"]].rank()
    correlacao = (postos.iloc[:, 0].corr(postos.iloc[:, 1])
                  if len(pares) > 1 and postos.nunique().min() > 1 else float("nan"))
    pares["divergencia_pp"] = (pares.perda_estimada_pct - pares.perda_producao_pct).abs()
    divergencias = pares.sort_values(["divergencia_pp", "ano", "cod_ibge"], ascending=[False, True, True]).head(
        cfg["realidade"]["maiores_divergencias"])
    return dict(dados=base, matriz=matriz, acuracia=float(estimado.eq(real).mean()),
                spearman=float(correlacao), pares_validos=len(pares), pares_excluidos=len(base) - len(pares),
                divergencias=divergencias, avisos=avisos)


if __name__ == "__main__":
    for cultura in carregar()["modelo_hidrico"]["culturas"]:
        try:
            placar = validacao(cultura)
            print(f"\n{cultura}: {placar['pares_validos']} pares; {placar['pares_excluidos']} excluídos")
            print(placar["matriz"].to_string())
            print(f"Acurácia: {placar['acuracia']:.2%}; Spearman: {placar['spearman']:.4f}")
            print("10 maiores divergências (pontos percentuais):")
            print(placar["divergencias"][["municipio", "uf", "ano", "perda_estimada_pct", "perda_producao_pct",
                                           "divergencia_pp", "pagou_garantia_safra"]].to_string(index=False,
                                                                                              float_format=lambda x: f"{x:.2f}"))
            for aviso in placar["avisos"]:
                print(f"AVISO: {aviso}")
        except (FileNotFoundError, ValueError) as erro:
            print(f"{cultura}: dados indisponíveis: {erro}")


def recortar_validacao(placar, cfg, filtros):
    """Recalcula métricas apenas para UF/safra, sem mutar o placar recebido."""
    placar = dict(placar)
    quadro = placar["dados"]
    quadro = quadro.loc[quadro.uf.isin(filtros["ufs"]) & quadro.ano.eq(filtros["ano"])].copy()
    pares = quadro.dropna(subset=["perda_estimada_pct", "perda_producao_pct"])
    limiar = cfg["risco"]["criterio_garantia_safra"]
    a, b = pares.perda_estimada_pct.ge(limiar), pares.perda_producao_pct.ge(limiar)
    matriz = pd.crosstab(a, b).reindex(index=[False, True], columns=[False, True], fill_value=0)
    divergencias = pares.assign(divergencia_pp=(pares.perda_estimada_pct - pares.perda_producao_pct).abs())
    placar.update(dados=quadro, matriz=matriz, acuracia=(a == b).mean(),
                  spearman=pares.perda_estimada_pct.rank().corr(pares.perda_producao_pct.rank()) if len(pares) > 1 else float("nan"),
                  pares_validos=len(pares), pares_excluidos=len(quadro)-len(pares),
                  divergencias=divergencias.nlargest(10, "divergencia_pp"))
    return placar
