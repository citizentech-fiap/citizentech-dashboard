"""Fatos agregados e resumo verificável, sem acesso à interface ou à rede."""
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from pipelines.recomendacoes import ROTULOS_TIPOS

CLASSES = {"seguro": "seguros", "atencao": "em atenção", "alerta": "em alerta", "critico": "críticos"}


def fatos(indicadores, demanda, recomendacoes, historico_decisoes, cfg, ano, ate_data, realidade=None):
    estimavel = bool(indicadores.estimavel.all())
    campo = "perda_estimada_pct" if estimavel else "anomalia_pct"
    top = indicadores.sort_values([campo, "cod_ibge"], ascending=[not estimavel, True]).head(5)
    agora = datetime.now(timezone.utc)
    recentes = Counter()
    decididas = {d["id"] for d in historico_decisoes}
    municipios = set(indicadores.municipio)
    for d in historico_decisoes:
        quando = pd.to_datetime(d.get("quando"), utc=True, errors="coerce")
        if (pd.notna(quando) and agora - timedelta(days=7) <= quando <= agora
                and d["id"].endswith(f"-{ano}") and d.get("municipio") in municipios):
            recentes[{"aprovada": "aprovadas", "editada": "ajustadas", "rejeitada": "recusadas"}[d["decisao"]]] += 1
    resultado = dict(safra=int(ano), data_corte=pd.Timestamp(ate_data).strftime("%d/%m/%Y"), estimavel=estimavel,
        janela_decisoes_dias=7,
        municipios_por_classe={CLASSES.get(str(k), str(k)): int(indicadores.classe.eq(k).sum())
                               for k in CLASSES if indicadores.classe.eq(k).any()},
        top_criticos=[dict(municipio=r.municipio, **{campo: round(float(getattr(r, campo)), 1)
                         if pd.notna(getattr(r, campo)) else None}) for r in top.itertuples()],
        acoes_pendentes={ROTULOS_TIPOS.get(k, k): v for k, v in
                         Counter(r.tipo for r in recomendacoes if r.id not in decididas).items()},
        decisoes_ultimos_7_dias={k: recentes[k] for k in ("aprovadas", "ajustadas", "recusadas")},
        travados_sem_caf=dict(total=int(demanda.travados_sem_caf.sum()),
                            simulado=cfg["fontes"]["pedidos"] != "rpa"))
    if realidade is not None and ano <= cfg["fontes"]["pam_fim"]:
        reais = realidade.loc[realidade.ano.eq(ano) & realidade.cod_ibge.isin(indicadores.cod_ibge)]
        valor = reais.perda_producao_pct.median()
        if pd.notna(valor):
            resultado["realidade"] = {"mediana_perda_real_pct": round(float(valor), 1)}
    return resultado


def numeros(texto):
    """Normaliza decimal, separador de milhar e sinal; % não muda o valor."""
    tokens = re.findall(r"(?<![\w])\d+(?:[.,]\d+)*", texto)
    valores = set()
    for token in tokens:
        if ',' in token:
            token = token.replace('.', '').replace(',', '.')
        elif re.fullmatch(r'[+-]?\d{1,3}(?:\.\d{3})+', token):
            token = token.replace('.', '')
        valores.add(str(Decimal(token).normalize()))
    return valores



def numeros_desconhecidos(texto, fatos):
    return sorted(numeros(texto) - numeros(json.dumps(fatos, ensure_ascii=False)))


def template(fatos):
    classes = ", ".join(f"{v} {k}" for k, v in fatos["municipios_por_classe"].items())
    sinal = "A perda já pode ser estimada" if fatos["estimavel"] else "É cedo para estimar perda; observe o sinal de chuva"
    pendentes = ", ".join(f"{v} × {k.lower()}" for k, v in fatos["acoes_pendentes"].items()) or "nenhuma ação"
    caf = fatos["travados_sem_caf"]
    decisoes = fatos["decisoes_ultimos_7_dias"]
    retrospectiva = (f"; a mediana da perda real IBGE foi {fatos['realidade']['mediana_perda_real_pct']}% na safra completa"
                     if 'realidade' in fatos else '')
    return (f"Safra {fatos['safra']}, até {fatos['data_corte']}: municípios {classes}. "
            f"{sinal}{retrospectiva}. Aguardam decisão: {pendentes}. "
            f"Há {caf['total']} pedidos travados sem CAF ({'simulado' if caf['simulado'] else 'robô de triagem'}). "
            f"Decisões na última semana: {decisoes['aprovadas']} aprovadas, {decisoes['ajustadas']} ajustadas e {decisoes['recusadas']} recusadas. "
            "Próximas ações: decidir as vistorias pendentes, começando pelos municípios mais críticos; "
            "organizar os mutirões do CAF; preparar as convocações aprovadas.")
