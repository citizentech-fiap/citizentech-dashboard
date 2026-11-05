"""Estimativa acadêmica FAO-33; não implementa o modelo oficial do INMET."""
import math

from providers.config import carregar


def calcular(chuva_mm, et0_mm, cultura, cfg):
    """Retorna déficit (mm) e perda (%) para totais do período.

    FAO-33: 1 - Ya/Ym = Ky * (1 - ETa/ETc).
    ETc = Kc * sum(ET0); chuva efetiva = fator * sum(chuva);
    ETa = min(ETc, chuva efetiva); déficit = ETc - ETa;
    perda = clip(100 * Ky * déficit/ETc, 0, 100).
    Sem demanda (ETc=0), perda=0. Não simula solo, irrigação, escoamento,
    fenologia ou distribuição intrassazonal: usa balanço agregado do período.
    A vistoria humana é o outro indicador exigido pelo Garantia-Safra.
    """
    modelo = cfg.get("modelo_hidrico", cfg)
    parametros = modelo["culturas"][cultura]
    chuva, et0 = float(chuva_mm), float(et0_mm)
    fator, ky, kc = (float(modelo["fator_chuva_efetiva"]),
                     float(parametros["ky"]), float(parametros["kc"]))
    if not all(math.isfinite(x) and x >= 0 for x in (chuva, et0, fator, ky, kc)):
        raise ValueError("Entradas e parâmetros hídricos devem ser finitos e não negativos.")
    if fator > 1:
        raise ValueError("Fator de chuva efetiva deve estar entre zero e um.")
    demanda = kc * et0
    deficit = max(0.0, demanda - fator * chuva)
    perda = min(100.0, max(0.0, 100 * ky * deficit / demanda)) if demanda else 0.0
    return {"deficit_hidrico_mm": deficit, "perda_estimada_pct": perda}


def perda_estimada(chuva_mm, et0_mm, cultura, cfg=None):
    return calcular(chuva_mm, et0_mm, cultura, cfg or carregar())["perda_estimada_pct"]


if __name__ == "__main__":
    cfg = carregar()
    for cultura in cfg["modelo_hidrico"]["culturas"]:
        print(cultura, "sem chuva:", calcular(0, 100, cultura, cfg))
