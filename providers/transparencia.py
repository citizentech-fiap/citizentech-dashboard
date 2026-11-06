"""Garantia-Safra: ZIP exclusivamente em memória; saída apenas municipal.

NIS serve só para deduplicar famílias dentro da safra e nunca sai da função.
O nome do beneficiário nem é lido pelo parser CSV.
"""
import io
import re
import time
import unicodedata
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import pandas as pd
import requests

from providers import dados_locais, http
from providers.config import carregar

COLUNAS = ["cod_ibge", "municipio", "uf", "safra", "familias", "valor_total", "meses_com_pagamento"]
URL = "https://portaldatransparencia.gov.br/download-de-dados/garantia-safra"
CAMPOS = ["MÊS REFERÊNCIA", "UF", "NOME MUNICÍPIO", "NIS FAVORECIDO", "VALOR PARCELA"]


def normalizar(texto):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", str(texto))
                            if not unicodedata.combining(c)).upper().split())


def safra_pagamento(ano_mes):
    mes = pd.Period(str(ano_mes), freq="M")
    return mes.year if mes.month >= 7 else mes.year - 1


def meses_publicados(*, cfg=None):
    """Catálogo público da página oficial; não contém dados de beneficiários."""
    html = http.get(URL, cache=False, cfg=cfg).decode("utf-8")
    pares = re.findall(r'arquivos.push\(\{"ano"\s*:\s*"(\d{4})",\s*"mes"\s*:\s*"(\d{2})"', html)
    if not pares:
        raise ValueError("Catálogo Garantia-Safra indisponível ou formato alterado.")
    return {ano + mes for ano, mes in pares}


def _acumular_zip(bruto, ano_mes, mapa, acumulado):
    """Função privada: dados individuais são consumidos e descartados em blocos."""
    safra = safra_pagamento(ano_mes)
    with zipfile.ZipFile(io.BytesIO(bruto)) as arquivo:
        csvs = [n for n in arquivo.namelist() if n.lower().endswith(".csv")]
        if not csvs:
            raise ValueError("ZIP Garantia-Safra sem CSV.")
        for nome in csvs:
            with arquivo.open(nome) as entrada:
                # Arquivo observado: separador ;, latin-1 (acentos compatíveis com cp1252).
                for bloco in pd.read_csv(entrada, sep=";", encoding="latin-1", dtype=str,
                                         usecols=CAMPOS, keep_default_na=False, chunksize=50000):
                    for referencia, uf, municipio, nis, valor in bloco[CAMPOS].itertuples(index=False, name=None):
                        alvo = mapa.get((normalizar(municipio), normalizar(uf)))
                        if alvo is None:
                            continue
                        if referencia.replace("-", "") != ano_mes:
                            raise ValueError("Mês de referência difere do mês solicitado.")
                        try:
                            parcela = Decimal(valor.replace(".", "").replace(",", "."))
                            if not parcela.is_finite() or parcela < 0:
                                raise InvalidOperation
                        except InvalidOperation:
                            raise ValueError("Valor de parcela inválido no Garantia-Safra.") from None
                        if parcela == 0:
                            continue
                        if not nis.strip():
                            raise ValueError("Parcela positiva sem identificador para deduplicação.")
                        chave = (int(alvo.cod_ibge), safra)
                        registro = acumulado[chave]
                        registro["nis"].add(nis.strip())
                        registro["valor"] += parcela
                        registro["meses"].add(ano_mes)


def agregar_zips(arquivos, municipios):
    """Recebe iterável (AAAAMM, bytes ZIP); retorna somente contagens e valores.

    Iterável permite baixar/descartar um ZIP de cada vez, mantendo só os NIS do
    recorte em memória. Deduplicação cobre todos os meses da mesma safra.
    """
    mapa = {(normalizar(m.municipio), normalizar(m.uf)): m
            for m in municipios.itertuples(index=False)}
    if len(mapa) != len(municipios):
        raise ValueError("Municípios ambíguos após normalização nome + UF.")
    acumulado = defaultdict(lambda: {"nis": set(), "valor": Decimal(0), "meses": set()})
    for ano_mes, bruto in arquivos:
        _acumular_zip(bruto, str(ano_mes), mapa, acumulado)
    cadastro = municipios.set_index("cod_ibge")
    linhas = []
    for (codigo, safra), r in sorted(acumulado.items()):
        m = cadastro.loc[codigo]
        linhas.append(dict(cod_ibge=codigo, municipio=m.municipio, uf=m.uf, safra=safra,
                           familias=len(r["nis"]), valor_total=float(r["valor"]),
                           meses_com_pagamento=len(r["meses"])))
    return pd.DataFrame(linhas, columns=COLUNAS)


def garantia_safra(ano_mes, municipios=None, *, cfg=None, progresso=None, publicados=None):
    """Um mês ou lista de meses. 404/410 são ausência; outras falhas propagam.

    attrs contém só cobertura mensal pública, nunca identificadores pessoais.
    """
    cfg = cfg or carregar()
    municipios = dados_locais.municipios() if municipios is None else municipios
    meses = [ano_mes] if isinstance(ano_mes, (str, int)) else list(ano_mes)
    cobertura = {}

    def arquivos():
        for mes in sorted({pd.Period(str(m), freq="M").strftime("%Y%m") for m in meses}):
            if publicados is not None and mes not in publicados:
                cobertura[mes] = "nao_publicado"
                if progresso:
                    progresso(f"Garantia-Safra {mes}: não consta no catálogo oficial")
                continue
            time.sleep(cfg["fontes"]["intervalo_download_s"])
            if progresso:
                progresso(f"Baixando Garantia-Safra {mes} (somente em memória)")
            try:
                for tentativa in range(cfg["fontes"]["retries"] + 1):
                    try:
                        bruto = http.get(URL + "/" + mes, cache=False, cfg=cfg)
                        break
                    except requests.RequestException as erro:
                        resposta = getattr(erro, "response", None)
                        if (resposta is None or resposta.status_code != 405
                                or tentativa == cfg["fontes"]["retries"]):
                            raise
                        espera = cfg["fontes"]["backoff_download_s"] * 2 ** tentativa
                        if progresso:
                            progresso(f"CGU {mes}: HTTP 405; nova tentativa em {espera}s")
                        time.sleep(espera)
            except requests.RequestException as erro:
                resposta = getattr(erro, "response", None)
                if resposta is not None and resposta.status_code in (404, 410):
                    cobertura[mes] = "inexistente"
                    continue
                raise
            if not zipfile.is_zipfile(io.BytesIO(bruto)):
                raise ValueError(f"Garantia-Safra {mes}: resposta não é ZIP; tente novamente.")
            cobertura[mes] = "disponivel"
            yield mes, bruto

    quadro = agregar_zips(arquivos(), municipios)
    quadro.attrs["cobertura"] = cobertura
    return quadro
