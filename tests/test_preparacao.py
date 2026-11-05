"""Preparação testada com APIs falsas e diretórios temporários."""
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from providers.config import carregar
from scripts import preparar_dados as preparar


class TestPreparacao(unittest.TestCase):
    def setUp(self):
        self.saida = patch("sys.stdout", new_callable=io.StringIO)
        self.saida.start()
        self.addCleanup(self.saida.stop)
        self.espera = patch("scripts.preparar_dados.time.sleep")
        self.espera.start()
        self.addCleanup(self.espera.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = carregar()
        for chave in ("malhas", "clima_diario", "climatologia"):
            self.cfg["paths"][chave] = Path(self.temp.name) / chave
        self.cfg["safra"]["anos_disponiveis"] = [2012, 2026]
        self.municipios = pd.DataFrame([dict(cod_ibge=1, municipio="Teste", uf="PE", lat=0, lon=0)])

    @staticmethod
    def diario(lat, lon, inicio, fim, **kwargs):
        return pd.DataFrame({"data": pd.date_range(inicio, fim), "chuva_mm": 2., "et0_mm": 4.})

    @patch("scripts.preparar_dados.open_meteo.diario", side_effect=diario)
    def test_clima_intervalos_retomada_e_forcar(self, diario):
        preparar.baixar_clima(self.municipios, self.cfg)
        self.assertEqual(diario.call_count, 2)
        quadro = pd.read_csv(self.cfg["paths"]["clima_diario"])
        self.assertEqual(len(quadro), 182 + 181)
        preparar.baixar_clima(self.municipios, self.cfg)
        self.assertEqual(diario.call_count, 2)
        preparar.baixar_clima(self.municipios, self.cfg, forcar=True)
        self.assertEqual(diario.call_count, 4)
        quadro.iloc[1:].to_csv(self.cfg["paths"]["clima_diario"], index=False)
        preparar.baixar_clima(self.municipios, self.cfg)
        self.assertEqual(diario.call_count, 5)

    @patch("scripts.preparar_dados.open_meteo.diario", side_effect=diario)
    def test_normal_uma_chamada_30_anos_e_idempotencia(self, diario):
        preparar.baixar_normal(self.municipios, self.cfg)
        diario.assert_called_once_with(0, 0, "1991-01-01", "2020-12-31", forcar=False)
        quadro = pd.read_csv(self.cfg["paths"]["climatologia"])
        self.assertEqual(len(quadro), 366)
        self.assertTrue(quadro.chuva_media_mm.eq(2).all())
        preparar.baixar_normal(self.municipios, self.cfg)
        self.assertEqual(diario.call_count, 1)

    def test_media_29_fevereiro_e_marco(self):
        diario = pd.DataFrame({"data": pd.to_datetime(["1991-03-01", "1992-02-29", "1992-03-01"]),
                               "chuva_mm": [2, 8, 4], "et0_mm": [1, 2, 3]})
        normal = preparar.agregar_normal(diario, 1).set_index("dia_ano")
        self.assertEqual(normal.loc[60, "chuva_media_mm"], 8)
        self.assertEqual(normal.loc[61, "chuva_media_mm"], 3)

    @patch("scripts.preparar_dados.ibge.malha")
    def test_malhas_properties_e_idempotencia(self, malha):
        malha.return_value = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": []}}]}
        preparar.baixar_malhas(self.municipios, self.cfg)
        preparar.baixar_malhas(self.municipios, self.cfg)
        malha.assert_called_once()
        colecao = json.loads(self.cfg["paths"]["malhas"].read_text(encoding="utf-8"))
        self.assertEqual(colecao["features"][0]["properties"], {"cod_ibge": 1, "municipio": "Teste"})

    def test_sinteticos_seed_anos_documentos_e_associacao_com_seca(self):
        municipios = pd.concat([self.municipios, self.municipios.assign(cod_ibge=2, municipio="Seco")])
        municipios = municipios.assign(perda_estimada_pct=[0, 100])
        catalogo = {"services": [{"id": s, "documentos_exigidos": ["cpf", "caf"]
                                  if s in ("pronaf", "garantia_safra") else ["cpf"]}
                                 for s in self.cfg["simulacao"]["pesos_servicos"]]}
        anos = {2012: municipios, 2026: municipios}
        pedidos = preparar.gerar_pedidos(anos, self.cfg, catalogo)
        pd.testing.assert_frame_equal(pedidos, preparar.gerar_pedidos(anos, self.cfg, catalogo))
        self.assertEqual(pedidos.ano.value_counts().to_dict(), {2012: 1000, 2026: 1000})
        self.assertTrue(pedidos.request_id.is_unique)
        self.assertNotIn("nome", pedidos)
        self.assertTrue(pedidos.fonte_resposta.eq("sintetica").all())
        self.assertGreater(pedidos.cod_ibge.eq(2).sum(), pedidos.cod_ibge.eq(1).sum())
        agro = pedidos.loc[pedidos.service_id.isin(["garantia_safra", "pronaf"])]
        proporcao = agro.docs_faltantes.str.split(";").map(lambda d: "caf" in d).mean()
        self.assertTrue(.25 <= proporcao <= .4, proporcao)
        docs = {s["id"]: set(s["documentos_exigidos"]) for s in catalogo["services"]}
        for p in pedidos.itertuples(index=False):
            presentes, faltantes = (set(v.split(";")) - {""} for v in (p.docs_presentes, p.docs_faltantes))
            self.assertFalse(presentes & faltantes)
            self.assertEqual(presentes | faltantes, docs[p.service_id])


if __name__ == "__main__":
    unittest.main()
