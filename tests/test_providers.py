"""Providers exercitados sem rede, sem Streamlit e sem ler .env."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

from providers import dados_locais, genai, http, ibge, open_meteo, rpa
from providers.config import RAIZ, carregar


class TestConfigHttp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = carregar()
        self.cfg["paths"]["cache_http"] = Path(self.temp.name)

    def resposta(self, conteudo=b'{"ok": true}', status=200):
        resposta = Mock(content=conteudo, status_code=status)
        resposta.headers = {}
        if status >= 400:
            resposta.raise_for_status.side_effect = requests.HTTPError(response=resposta)
        return resposta

    def test_config_independe_cwd(self):
        self.assertEqual(carregar()["paths"]["municipios"], RAIZ / "data/municipios_semiarido.csv")
        self.assertTrue(all(p.is_absolute() for p in carregar()["paths"].values()))

    @patch("providers.http.requests.get")
    def test_gzip_cache_e_forcar(self, get):
        get.return_value = self.resposta(gzip.compress(b'{"ok": true}'))
        self.assertEqual(http.get("https://exemplo", cfg=self.cfg), b'{"ok": true}')
        self.assertEqual(http.get("https://exemplo", cfg=self.cfg), b'{"ok": true}')
        self.assertEqual(get.call_count, 1)
        http.get("https://exemplo", cfg=self.cfg, forcar=True)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.kwargs["timeout"], self.cfg["fontes"]["timeout_s"])
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"], http.USER_AGENT)

    @patch("providers.http.time.sleep")
    @patch("providers.http.requests.get")
    def test_retry_rede_429_503(self, get, sleep):
        get.side_effect = [requests.ConnectionError("rede"), self.resposta(status=429),
                           self.resposta(status=503), self.resposta()]
        http.get("https://exemplo", cache=False, cfg=self.cfg)
        self.assertEqual(get.call_count, 4)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [2, 4, 8])
        self.assertFalse(list(Path(self.temp.name).iterdir()))

    @patch("providers.http.time.sleep")
    @patch("providers.http.requests.get")
    def test_404_nao_repete(self, get, sleep):
        get.return_value = self.resposta(status=404)
        with self.assertRaises(requests.RequestException):
            http.get("https://exemplo", cfg=self.cfg)
        self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()

    @patch("providers.http.time.sleep")
    @patch("providers.http.requests.get", side_effect=requests.Timeout("timeout"))
    def test_esgota_retry(self, get, sleep):
        with self.assertRaisesRegex(requests.RequestException, "Falha no GET"):
            http.get("https://exemplo", cfg=self.cfg)
        self.assertEqual(get.call_count, 4)

    @patch("providers.http.time.sleep")
    @patch("providers.http.requests.get")
    def test_retry_after(self, get, sleep):
        limitada = self.resposta(status=429)
        limitada.headers = {"Retry-After": "30"}
        get.side_effect = [limitada, self.resposta()]
        http.get("https://exemplo", cache=False, cfg=self.cfg)
        sleep.assert_called_once_with(30)


class TestFontes(unittest.TestCase):
    @patch("providers.open_meteo.http.get")
    def test_diario_uma_chamada_e_parametros(self, get):
        get.return_value = json.dumps({"daily": {"time": ["2012-01-01", "2012-01-02"],
                                               "precipitation_sum": [0, 2],
                                               "et0_fao_evapotranspiration": [3, 4]}}).encode()
        quadro = open_meteo.diario(-9, -40, "2012-01-01", "2012-01-02")
        self.assertEqual(list(quadro), ["data", "chuva_mm", "et0_mm"])
        self.assertEqual(quadro.chuva_mm.sum(), 2)
        get.assert_called_once()
        self.assertEqual(get.call_args.args[1]["timezone"], "America/Recife")
        self.assertEqual(get.call_args.args[1]["daily"], "precipitation_sum,et0_fao_evapotranspiration")

    @patch("providers.open_meteo.http.get")
    def test_diario_rejeita_lacuna_e_null(self, get):
        for datas, chuva in [(["2012-01-01"], [0]), (["2012-01-01", "2012-01-02"], [None, 2])]:
            get.return_value = json.dumps({"daily": {"time": datas, "precipitation_sum": chuva,
                                                   "et0_fao_evapotranspiration": [3] * len(datas)}}).encode()
            with self.assertRaisesRegex(ValueError, "Resposta climática inválida"):
                open_meteo.diario(0, 0, "2012-01-01", "2012-01-02")

    @patch("providers.ibge.http.get")
    def test_ibge(self, get):
        get.return_value = b'{"type":"FeatureCollection","features":[{"type":"Feature"}]}'
        self.assertEqual(ibge.malha(2611101)["type"], "FeatureCollection")
        self.assertIn("2611101", get.call_args.args[0])

    def test_snapshots_ausentes(self):
        cfg = carregar()
        with tempfile.TemporaryDirectory() as pasta:
            for chave in cfg["paths"]:
                cfg["paths"][chave] = Path(pasta) / chave
            with patch("providers.dados_locais.carregar", return_value=cfg):
                for leitor in (dados_locais.municipios, dados_locais.malhas,
                               dados_locais.clima_diario, dados_locais.climatologia):
                    with self.assertRaisesRegex(FileNotFoundError, "preparar_dados"):
                        leitor()
            with patch("providers.rpa.carregar", return_value=cfg):
                with self.assertRaisesRegex(FileNotFoundError, "Fonte 'rpa'"):
                    rpa.pedidos("rpa")

    def test_rpa_le_xlsx_sem_pii_e_deriva_ano(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "controle.xlsx"
            linha = {c: "" for c in rpa.COLUNAS}
            linha.update(request_id="A", data_envio="2026-03-01", municipio="X", uf="PE",
                         cod_ibge="2611101", service_id="pronaf", nome="NÃO EXPOR")
            pd.DataFrame([linha]).to_excel(arquivo, sheet_name="solicitacoes", index=False)
            cfg = carregar()
            cfg["paths"]["rpa_controle"] = arquivo
            with patch("providers.rpa.carregar", return_value=cfg):
                resultado = rpa.pedidos("rpa")
            self.assertEqual(resultado.ano.tolist(), [2026])
            self.assertNotIn("nome", resultado)
            self.assertEqual(resultado.docs_faltantes.tolist(), [""])

    @patch("providers.genai.import_module", side_effect=ImportError("indisponível"))
    def test_genai_opcional(self, importar):
        rag, motivo = genai.criar_rag()
        self.assertIsNone(rag)
        self.assertIn("RAG indisponível", motivo)

    def test_genai_nao_carrega_env(self):
        configuracao = Mock()
        configuracao.load_env = Mock(side_effect=AssertionError("Não ler .env"))
        modulo = Mock()
        def construir(**kwargs):
            configuracao.load_env()
            return Mock(_init_error=None)
        modulo.RAGAssistant.side_effect = construir
        with patch("providers.genai.import_module", side_effect=[modulo, configuracao]):
            rag, motivo = genai.criar_rag()
        self.assertIsNotNone(rag)
        configuracao.load_env.assert_not_called()
        self.assertIn("overrides", modulo.RAGAssistant.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
