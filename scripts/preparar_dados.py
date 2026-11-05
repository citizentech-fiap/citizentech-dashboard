"""Baixa snapshots reais e gera pedidos explicitamente sintéticos.

Execute da raiz: python scripts/preparar_dados.py [--forcar]. Cada município/
intervalo concluído é persistido; uma falha não elimina o progresso anterior.
"""
import argparse
import json
from pathlib import Path
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import yaml

from pipelines.clima import dias_calendario
from pipelines.risco import indicadores
from providers import dados_locais, ibge, open_meteo
from providers.config import carregar
from providers.http import gravar_atomico


def salvar_csv(quadro, arquivo):
    gravar_atomico(arquivo, quadro.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"))


def agregar_normal(diario, codigo):
    """Normal por mês/dia; 29/02 usa apenas os oito anos bissextos de 1991–2020."""
    diario = diario.copy()
    diario["dia_ano"] = dias_calendario(diario.data).to_numpy()
    normal = diario.groupby("dia_ano", as_index=False)[["chuva_mm", "et0_mm"]].mean()
    normal = normal.rename(columns={"chuva_mm": "chuva_media_mm", "et0_mm": "et0_media_mm"})
    normal.insert(0, "cod_ibge", int(codigo))
    return normal


def _ler_existente(arquivo, colunas, datas=False):
    if not arquivo.exists():
        quadro = pd.DataFrame(columns=colunas)
    else:
        quadro = pd.read_csv(arquivo)
    if not set(colunas).issubset(quadro):
        raise ValueError(f"Snapshot inválido: {arquivo}; use --forcar.")
    if datas:
        quadro["data"] = pd.to_datetime(quadro.data)
    return quadro


def baixar_malhas(municipios, cfg, forcar=False):
    arquivo = cfg["paths"]["malhas"]
    colecao = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {
        "type": "FeatureCollection", "features": []}
    for m in municipios.itertuples(index=False):
        existente = [f for f in colecao["features"] if int(f["properties"]["cod_ibge"]) == m.cod_ibge]
        if existente and not forcar:
            print(f"Malha {m.municipio}: existente", flush=True)
            continue
        print(f"Baixando malha: {m.municipio}", flush=True)
        novas = ibge.malha(m.cod_ibge, forcar=forcar)["features"]
        for feature in novas:
            feature.setdefault("properties", {}).update(cod_ibge=int(m.cod_ibge), municipio=m.municipio)
        colecao["features"] = [f for f in colecao["features"] if f not in existente] + novas
        gravar_atomico(arquivo, json.dumps(colecao, ensure_ascii=False).encode("utf-8"))


def baixar_clima(municipios, cfg, forcar=False):
    arquivo = cfg["paths"]["clima_diario"]
    colunas = ["cod_ibge", "data", "chuva_mm", "et0_mm"]
    quadro = _ler_existente(arquivo, colunas, datas=True)
    for m in municipios.itertuples(index=False):
        for ano in cfg["safra"]["anos_disponiveis"]:
            inicio, fim = (pd.Timestamp(f"{ano}-{cfg['safra'][chave]}")
                           for chave in ("inicio_mes_dia", "fim_mes_dia"))
            mascara = quadro.cod_ibge.eq(m.cod_ibge) & quadro.data.between(inicio, fim)
            existente = quadro.loc[mascara].sort_values("data")
            completo = (existente.data.reset_index(drop=True).equals(pd.Series(pd.date_range(inicio, fim)))
                        and not existente.isna().any().any())
            if completo and not forcar:
                print(f"Clima {m.municipio}/{ano}: existente", flush=True)
                continue
            print(f"Baixando clima: {m.municipio}/{ano}", flush=True)
            novo = open_meteo.diario(m.lat, m.lon, inicio, fim, forcar=forcar)
            novo.insert(0, "cod_ibge", int(m.cod_ibge))
            quadro = pd.concat([quadro.loc[~mascara], novo], ignore_index=True)
            salvar_csv(quadro.sort_values(["cod_ibge", "data"]), arquivo)


def baixar_normal(municipios, cfg, forcar=False):
    arquivo = cfg["paths"]["climatologia"]
    colunas = ["cod_ibge", "dia_ano", "chuva_media_mm", "et0_media_mm"]
    quadro = _ler_existente(arquivo, colunas)
    for m in municipios.itertuples(index=False):
        existente = quadro.loc[quadro.cod_ibge.eq(m.cod_ibge)]
        if (not forcar and len(existente) == 366 and set(existente.dia_ano) == set(range(1, 367))
                and not existente.isna().any().any()):
            print(f"Normal {m.municipio}: existente", flush=True)
            continue
        print(f"Baixando normal 1991–2020: {m.municipio} (uma chamada)", flush=True)
        time.sleep(cfg["fontes"]["intervalo_normal_s"])
        diario = open_meteo.diario(m.lat, m.lon, f"{cfg['safra']['normal_inicio']}-01-01",
                                  f"{cfg['safra']['normal_fim']}-12-31", forcar=forcar)
        normal = agregar_normal(diario, m.cod_ibge)
        quadro = pd.concat([quadro.loc[~quadro.cod_ibge.eq(m.cod_ibge)], normal], ignore_index=True)
        salvar_csv(quadro.sort_values(["cod_ibge", "dia_ano"]), arquivo)


def gerar_pedidos(indicadores_anos, cfg, catalogo):
    """1.000 pedidos por ano; uma solicitação representa uma família fictícia.

    Sorteio multinomial com peso 1+3*perda/100 por município. GS, CAF e Pronaf
    ganham peso com a perda. Documentos são os canônicos do catálogo do RPA.
    Não cria nomes, CPF, contato ou qualquer identificador pessoal.
    """
    sim = cfg["simulacao"]
    rng = np.random.default_rng(sim["seed"])
    servicos = {s["id"]: s["documentos_exigidos"] for s in catalogo["services"]}
    ids = list(sim["pesos_servicos"])
    faltam = set(ids) - set(servicos)
    if faltam:
        raise ValueError(f"Serviços ausentes no catálogo do RPA: {sorted(faltam)}")
    linhas = []
    for ano, municipios in sorted(indicadores_anos.items()):
        municipios = municipios.sort_values("cod_ibge").reset_index(drop=True)
        pesos = sim["peso_volume_base"] + sim["peso_volume_perda"] * municipios.perda_estimada_pct / 100
        escolhas = rng.choice(len(municipios), size=sim["pedidos_por_ano"], p=pesos / pesos.sum())
        inicio = pd.Timestamp(f"{ano}-{cfg['safra']['inicio_mes_dia']}")
        fim = pd.Timestamp(f"{ano}-{cfg['safra']['fim_mes_dia']}")
        for numero, indice in enumerate(escolhas, 1):
            m = municipios.iloc[indice]
            pesos_servicos = np.array([sim["pesos_servicos"][s] for s in ids], dtype=float)
            for i, servico in enumerate(ids):
                if servico in ("garantia_safra", "caf", "pronaf"):
                    pesos_servicos[i] *= 1 + sim["incremento_servicos_seca"] * m.perda_estimada_pct / 100
            servico = str(rng.choice(ids, p=pesos_servicos / pesos_servicos.sum()))
            exigidos = servicos[servico]
            faltantes = []
            if servico in ("garantia_safra", "pronaf") and rng.random() < sim["prob_sem_caf"]:
                faltantes.append("caf")
            outros = [d for d in exigidos if d != "caf"]
            if outros and rng.random() < sim["prob_outro_doc_faltante"]:
                faltantes.append(str(rng.choice(outros)))
            presentes = [d for d in exigidos if d not in faltantes]
            ilegiveis = ([str(rng.choice(presentes))] if presentes and
                         rng.random() < sim["prob_doc_ilegivel"] else [])
            revisao = bool(ilegiveis) or rng.random() < sim["prob_revisao_adicional"]
            data = inicio + pd.Timedelta(days=int(rng.integers((fim - inicio).days + 1)))
            linhas.append({"request_id": f"SINT-{ano}-{numero:04d}", "ano": int(ano),
                           "data_envio": data.strftime("%Y-%m-%dT10:00:00-03:00"),
                           "municipio": m.municipio, "uf": m.uf, "cod_ibge": int(m.cod_ibge),
                           "service_id": servico,
                           "confianca": round(float(rng.uniform(sim["confianca_min"], sim["confianca_max"])), 3),
                           "decisao": "revisao_humana" if revisao else "resolvido",
                           "motivo": "Simulação sintética; " + ("documentação pendente" if faltantes else "triagem"),
                           "docs_presentes": ";".join(presentes), "docs_faltantes": ";".join(faltantes),
                           "docs_ilegiveis": ";".join(ilegiveis), "fonte_resposta": "sintetica"})
    return pd.DataFrame(linhas)


def preparar(forcar=False):
    cfg = carregar()
    municipios = dados_locais.municipios()
    falhas = []
    for etapa in (baixar_malhas, baixar_clima, baixar_normal):
        try:
            etapa(municipios, cfg, forcar)
        except Exception as erro:
            falhas.append(f"{etapa.__name__}: {erro}")
            print(f"AVISO: {falhas[-1]}. Progresso salvo; execute novamente para retomar.", flush=True)
    arquivo = cfg["paths"]["pedidos_snapshot"]
    if forcar or not arquivo.exists():
        try:
            anos = sorted({cfg["safra"]["ano_padrao"], cfg["safra"]["ano_demo_seca"]})
            indicadores_anos = {ano: indicadores(ano, cfg["modelo_hidrico"]["cultura_padrao"]) for ano in anos}
            config_rpa = cfg["paths"]["rpa_controle"].parents[1] / "config.yaml"
            if not config_rpa.is_file():
                raise FileNotFoundError(f"Catálogo de documentos do RPA ausente: {config_rpa}")
            catalogo = yaml.safe_load(config_rpa.read_text(encoding="utf-8"))
            salvar_csv(gerar_pedidos(indicadores_anos, cfg, catalogo), arquivo)
            print(f"Pedidos SINTÉTICOS gerados: {arquivo}", flush=True)
        except Exception as erro:
            falhas.append(f"pedidos: {erro}")
            print(f"AVISO: {falhas[-1]}; nenhum clima será inventado.", flush=True)
    else:
        print("Pedidos sintéticos: existente", flush=True)
    for chave in ("malhas", "clima_diario", "climatologia", "pedidos_snapshot"):
        caminho = cfg["paths"][chave]
        print(f"{chave}: {caminho.stat().st_size if caminho.exists() else 0:,} bytes", flush=True)
    return 1 if falhas else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forcar", action="store_true", help="Renova snapshots e cache HTTP")
    sys.exit(preparar(parser.parse_args().forcar))
