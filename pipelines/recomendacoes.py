"""Regras explicáveis; recomendações sempre aguardam decisão humana."""
import argparse
from dataclasses import dataclass
import math

from pipelines import demanda, risco
from providers.config import carregar
from providers.rpa import pedidos


@dataclass(frozen=True)
class Recomendacao:
    id: str
    tipo: str
    cod_ibge: int
    municipio: str
    prioridade: float
    titulo: str
    justificativa: str
    evidencias: dict
    acao_sugerida: str


def gerar(indicadores, demanda, cfg, ano):
    """Score comum = soma ponderada / soma dos pesos.

    Risco = perda/100; famílias e gargalo = valor/máximo municipal no conjunto
    atual (zero se máximo zero). As três regras compartilham o mesmo score;
    empates são ordenados por código e tipo. Comparar scores entre anos exige
    cuidado, pois os máximos de demanda mudam.
    """
    pesos = cfg["recomendacoes"]["pesos_prioridade"]
    if (not all(math.isfinite(float(p)) and p >= 0 for p in pesos.values())
            or sum(pesos.values()) <= 0):
        raise ValueError("Pesos de prioridade devem ser não negativos e ter soma positiva.")
    municipios = demanda.set_index("cod_ibge").to_dict("index")
    max_familias = max((m["familias_garantia_safra"] for m in municipios.values()), default=0)
    max_gargalo = max((m["travados_sem_caf"] for m in municipios.values()), default=0)
    criterio = cfg["risco"]["criterio_garantia_safra"]
    recomendacoes = []
    for ind in indicadores.to_dict("records"):
        dem = municipios.get(ind["cod_ibge"], {})
        familias = int(dem.get("familias_garantia_safra", 0))
        gargalo = int(dem.get("travados_sem_caf", 0))
        completos = int(dem.get("docs_completos", 0))
        perda = float(ind["perda_estimada_pct"])
        score = (pesos["risco"] * perda / 100 +
                 pesos["familias"] * (familias / max_familias if max_familias else 0) +
                 pesos["gargalo"] * (gargalo / max_gargalo if max_gargalo else 0)) / sum(pesos.values())
        anomalia = ind["anomalia_pct"]
        chuva = (f"chuva {abs(anomalia):.0f}% {'abaixo' if anomalia < 0 else 'acima'} da normal"
                 if math.isfinite(anomalia) else "normal de chuva indisponível")
        justificativa = (f"Perda estimada de {perda:.0f}% (critério {criterio}%); {chuva}; "
                         f"{familias} famílias inscritas na simulação do Garantia-Safra. "
                         "Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria.")
        regras = []
        nome = ind["municipio"]
        if perda >= criterio:
            regras.append(("vistoria", f"Indicar técnico vistoriador para a vistoria de perdas em {nome}",
                           "Solicitar vistoria amostral de perdas em campo."))
        if gargalo >= cfg["recomendacoes"]["min_pedidos_mutirao"]:
            regras.append(("mutirao_caf", f"Mutirão de inscrição no CAF em {nome}",
                           "Organizar atendimento de inscrição no CAF; sem CAF não há Garantia-Safra nem Pronaf."))
        if ind["classe"] in ("alerta", "critico") and completos > 0:
            regras.append(("convocacao", f"Convocar {completos} agricultores de {nome} com documentação completa",
                           f"Preparar convocação para atendimento em {nome}, sujeita à aprovação do gestor."))
        for tipo, titulo, acao in regras:
            recomendacoes.append(Recomendacao(
                id=f"{tipo}-{int(ind['cod_ibge'])}-{ano}", tipo=tipo,
                cod_ibge=int(ind["cod_ibge"]), municipio=nome,
                prioridade=min(1.0, max(0.0, score)), titulo=titulo,
                justificativa=justificativa + f" {gargalo} travados sem CAF; {completos} com documentação completa.",
                evidencias={**ind, "ano": int(ano), "familias_garantia_safra": familias,
                            "travados_sem_caf": gargalo, "docs_completos": completos},
                acao_sugerida=acao))
    # Mesmo score para as ações de um município; desempate na ordem do processo real:
    # vistoria (sem laudo não há pagamento) -> mutirão do CAF (destrava pedidos) -> convocação.
    return sorted(recomendacoes, key=lambda r: (-r.prioridade, r.cod_ibge, ORDEM_TIPOS.get(r.tipo, 9)))


ORDEM_TIPOS = {"vistoria": 0, "mutirao_caf": 1, "convocacao": 2}
ROTULOS_TIPOS = {"vistoria": "Vistoria de perdas", "mutirao_caf": "Mutirão do CAF", "convocacao": "Convocação"}


if __name__ == "__main__":
    cfg = carregar()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=cfg["safra"]["ano_padrao"])
    parser.add_argument("--cultura", default=cfg["modelo_hidrico"]["cultura_padrao"])
    args = parser.parse_args()
    try:
        todos = pedidos()
        recs = gerar(risco.indicadores(args.ano, args.cultura),
                     demanda.resumo(todos.loc[todos.ano == args.ano]), cfg, args.ano)
        print(f"Safra {args.ano}: {len(recs)} recomendações; top 5:")
        for rec in recs[:5]:
            print(f"{rec.prioridade:.3f} | {rec.tipo} | {rec.municipio} | {rec.titulo}\n  {rec.justificativa}")
    except (FileNotFoundError, ValueError) as erro:
        print(f"Dados indisponíveis: {erro}")
