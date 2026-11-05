"""Estimativa acadêmica por ISNA relativo à normal; não é o modelo oficial INMET."""
import math

from providers.config import carregar


def calcular(chuva_mm, et0_mm, cultura, cfg, *, chuva_normal_mm, et0_normal_mm):
    """Retorna déficit, ISNAs, razão e perda relativa à normal 1991–2020.

    ISNA (Índice de Satisfação das Necessidades de Água) = ETa/ETc.
    Para o ano e a normal, separadamente: ETc = Kc * sum(ET0);
    ETa = min(ETc, fator * sum(chuva)). Os totais da normal são as médias
    diárias de chuva e ET0 de 1991–2020, no MESMO período do ano/corte.
    razao_isna = ISNA_ano/ISNA_normal;
    perda = clip(100 * Ky * (1 - razao_isna), 0, 100).
    Adapta a resposta hídrica FAO-33 a uma referência histórica, evitando
    penalizar o déficit estrutural de uma safra normal no semiárido.
    Sem demanda (ETc=0), ISNA=1; normal com ISNA=0 é referência indefinida
    e levanta ValueError. O déficit em mm continua absoluto, só diagnóstico.
    Não simula solo, irrigação, escoamento, fenologia ou distribuição diária.
    Não é o modelo oficial INMET nem comprovação de perda ou de direito ao
    benefício; a vistoria e a decisão de pagamento permanecem externas.
    """
    modelo = cfg.get("modelo_hidrico", cfg)
    parametros = modelo["culturas"][cultura]
    chuva, et0 = float(chuva_mm), float(et0_mm)
    chuva_normal, et0_normal = float(chuva_normal_mm), float(et0_normal_mm)
    fator, ky, kc = (float(modelo["fator_chuva_efetiva"]),
                     float(parametros["ky"]), float(parametros["kc"]))
    if not all(math.isfinite(x) and x >= 0 for x in
               (chuva, et0, chuva_normal, et0_normal, fator, ky, kc)):
        raise ValueError("Entradas e parâmetros hídricos devem ser finitos e não negativos.")
    if fator > 1:
        raise ValueError("Fator de chuva efetiva deve estar entre zero e um.")
    demanda = kc * et0
    demanda_normal = kc * et0_normal
    deficit = max(0.0, demanda - fator * chuva)
    isna_ano = min(1.0, fator * chuva / demanda) if demanda else 1.0
    isna_normal = min(1.0, fator * chuva_normal / demanda_normal) if demanda_normal else 1.0
    if isna_normal == 0:
        raise ValueError("ISNA da normal é zero; perda relativa à normal é indefinida.")
    razao = isna_ano / isna_normal
    perda = min(100.0, max(0.0, 100 * ky * (1 - razao)))
    return {"deficit_hidrico_mm": deficit, "isna_ano": isna_ano,
            "isna_normal": isna_normal, "razao_isna": razao, "perda_estimada_pct": perda}


def perda_estimada(chuva_mm, et0_mm, cultura, cfg=None, *, chuva_normal_mm, et0_normal_mm):
    return calcular(chuva_mm, et0_mm, cultura, cfg or carregar(),
                    chuva_normal_mm=chuva_normal_mm,
                    et0_normal_mm=et0_normal_mm)["perda_estimada_pct"]


if __name__ == "__main__":
    cfg = carregar()
    for cultura in cfg["modelo_hidrico"]["culturas"]:
        print(cultura, "sem chuva vs. normal:", calcular(
            0, 100, cultura, cfg, chuva_normal_mm=50, et0_normal_mm=100))
