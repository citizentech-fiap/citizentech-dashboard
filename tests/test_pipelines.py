"""Regras de domínio e integração entre séries, risco, demanda e recomendações."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from pipelines import clima, decisoes, demanda, modelo_hidrico, recomendacoes, risco
from providers.config import carregar


def dados_clima(ano=2012):
    datas = pd.date_range(f"{ano}-01-01", f"{ano}-06-30")
    diario = pd.DataFrame({"cod_ibge": 1, "data": datas, "chuva_mm": 1.0, "et0_mm": 5.0})
    normal = pd.DataFrame({"cod_ibge": 1, "dia_ano": range(1, 367),
                           "chuva_media_mm": 2.0, "et0_media_mm": 4.0})
    municipios = pd.DataFrame([{"cod_ibge": 1, "municipio": "Teste", "uf": "PE"}])
    return diario, normal, municipios


class TestClimaModelo(unittest.TestCase):
    def test_modelo_extremos_e_monotonicidade(self):
        cfg = carregar()
        for cultura, parametros in cfg["modelo_hidrico"]["culturas"].items():
            self.assertEqual(modelo_hidrico.perda_estimada(1000, 100, cultura, cfg), 0)
            self.assertEqual(modelo_hidrico.perda_estimada(0, 100, cultura, cfg),
                             min(100, parametros["ky"] * 100))
            perdas = [modelo_hidrico.perda_estimada(p, 100, cultura, cfg) for p in range(200)]
            self.assertTrue(all(a >= b for a, b in zip(perdas, perdas[1:])))
            self.assertEqual(modelo_hidrico.perda_estimada(0, 0, cultura, cfg), 0)
        cfg["modelo_hidrico"]["culturas"]["milho"]["ky"] = 0.5
        self.assertEqual(modelo_hidrico.perda_estimada(0, 100, "milho", cfg), 50)

    def test_formula_intermediaria(self):
        cfg = carregar()
        resultado = modelo_hidrico.calcular(50, 100, "milho", cfg)
        self.assertEqual(resultado["deficit_hidrico_mm"], 45)
        self.assertAlmostEqual(resultado["perda_estimada_pct"], 100 * 1.25 * 45 / 85)
        # O limite é chuva EFETIVA >= demanda, não chuva bruta >= ETc.
        self.assertEqual(modelo_hidrico.perda_estimada(85 / .8, 100, "milho", cfg), 0)
        for valor in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                modelo_hidrico.calcular(valor, 100, "milho", cfg)

    def test_sequencia_seca(self):
        self.assertEqual(clima.maior_sequencia_seca([0, 0.5, 1, 0, 0, 0, 5], 1), 3)
        self.assertEqual(clima.maior_sequencia_seca([], 1), 0)
        with self.assertRaises(ValueError):
            clima.maior_sequencia_seca([float("nan")], 1)
        with self.assertRaises(ValueError):
            clima.maior_sequencia_seca([float("inf")], 1)

    def test_calendario_bissexto_sem_deslocar_marco(self):
        datas = pd.Series(pd.to_datetime(["2012-02-29", "2012-03-01", "2013-03-01"]))
        self.assertEqual(clima.dias_calendario(datas).tolist(), [60, 61, 61])
        for ano, dias in [(2012, 182), (2026, 181)]:
            diario, normal, _ = dados_clima(ano)
            serie = clima.montar_serie(diario, normal, 1, ano, carregar())
            self.assertEqual(serie.chuva_acum.iloc[-1], dias)
            self.assertEqual(serie.normal_acum.iloc[-1], dias * 2)

    def test_serie_rejeita_lacunas(self):
        diario, normal, _ = dados_clima()
        with self.assertRaisesRegex(ValueError, "Clima incompleto"):
            clima.montar_serie(diario.iloc[1:], normal, 1, 2012, carregar())
        with self.assertRaisesRegex(ValueError, "normal inválidos"):
            clima.montar_serie(diario, normal.iloc[:3], 1, 2012, carregar())


class TestRisco(unittest.TestCase):
    def test_limites(self):
        cfg = carregar()
        for valor, classe in [(0, "seguro"), (19.99, "seguro"), (20, "atencao"),
                              (39.99, "atencao"), (40, "alerta"), (60, "critico"), (100, "critico")]:
            self.assertEqual(risco.classificar(valor, cfg), classe)
        for valor in (-1, 101, float("nan")):
            with self.assertRaises(ValueError):
                risco.classificar(valor, cfg)

    @patch("pipelines.risco.dados_locais")
    def test_indicadores_e_replay_sem_olhar_futuro(self, locais):
        diario, normal, municipios = dados_clima()
        locais.clima_diario.return_value = diario
        locais.climatologia.return_value = normal
        locais.municipios.return_value = municipios
        parcial = risco.indicadores(2012, "milho", "2012-01-02").iloc[0]
        self.assertEqual(parcial.chuva_mm, 2)
        self.assertEqual(parcial.normal_mm, 4)
        self.assertEqual(parcial.anomalia_pct, -50)
        self.assertEqual(parcial.classe, "critico")
        final = risco.indicadores(2012, "milho")
        replay = risco.evolucao(2012, "milho")
        self.assertEqual(replay.data.iloc[-1], pd.Timestamp("2012-06-30"))
        self.assertAlmostEqual(replay.perda_estimada_pct.iloc[-1], final.perda_estimada_pct.iloc[0])
        self.assertEqual(replay.chuva_mm.iloc[0], 1)
        with self.assertRaises(ValueError):
            risco.indicadores(2012, "milho", "2011-12-31")


def pedidos_teste():
    linhas = []
    for i, (servico, falta, ilegivel, decisao) in enumerate([
        ("garantia_safra", "caf; cpf", "", "resolvido"),
        ("pronaf", " caf ", "", "resolvido"),
        ("cpf", "caf", "", "resolvido"),
        ("garantia_safra", "", "", "resolvido"),
        ("pronaf", "", "cpf", "revisao_humana"),
        ("pronaf", "caf_extra", "", "resolvido"),
    ]):
        linhas.append(dict(request_id=str(i), cod_ibge=1, municipio="Teste", uf="PE",
                           service_id=servico, docs_faltantes=falta, docs_ilegiveis=ilegivel, decisao=decisao))
    return pd.DataFrame(linhas)


class TestDemandaRecomendacoes(unittest.TestCase):
    def test_demanda_tokens_e_documentacao(self):
        pedidos = pedidos_teste()
        resultado = demanda.resumo(pedidos).iloc[0]
        self.assertEqual(resultado.pedidos, 6)
        self.assertEqual(resultado.travados_sem_caf, 2)
        self.assertEqual(resultado.familias_garantia_safra, 2)
        self.assertEqual(resultado.docs_completos, 1)
        self.assertEqual(resultado.revisao_humana, 1)
        self.assertEqual(resultado.docs_mais_faltantes["caf"], 3)
        self.assertEqual(demanda.por_servico(pedidos).pedidos.sum(), 6)
        self.assertTrue(demanda.resumo(pedidos.iloc[:0]).empty)

    def test_regras_ordenacao_pesos_e_ids(self):
        cfg = carregar()
        inds = pd.DataFrame([dict(cod_ibge=c, municipio=str(c), uf="PE", perda_estimada_pct=p,
                                  anomalia_pct=-58, classe=risco.classificar(p, cfg))
                             for c, p in [(1, 39), (2, 40), (3, 63)]])
        dem = pd.DataFrame([dict(cod_ibge=c, familias_garantia_safra=f,
                                 travados_sem_caf=g, docs_completos=d)
                            for c, f, g, d in [(1, 0, 9, 2), (2, 20, 10, 0), (3, 41, 11, 4)]])
        recs = recomendacoes.gerar(inds, dem, cfg, 2012)
        self.assertEqual(len(recs), 5)
        self.assertTrue(all(a.prioridade >= b.prioridade for a, b in zip(recs, recs[1:])))
        self.assertTrue(all(0 <= r.prioridade <= 1 for r in recs))
        self.assertEqual({r.tipo for r in recs if r.cod_ibge == 3}, {"vistoria", "mutirao_caf", "convocacao"})
        self.assertFalse(any(r.cod_ibge == 1 for r in recs))
        self.assertFalse(any(r.tipo == "convocacao" and r.cod_ibge == 2 for r in recs))
        self.assertIn("Perda estimada de 63%", recs[0].justificativa)
        self.assertIn("41 famílias", recs[0].justificativa)
        self.assertEqual(recs, recomendacoes.gerar(inds, dem, cfg, 2012))
        self.assertTrue(all(r.id.endswith("-2012") for r in recs))
        self.assertAlmostEqual(recs[0].prioridade, .5 * .63 + .3 + .2)
        cfg["recomendacoes"]["pesos_prioridade"] = {"risco": 5, "familias": 3, "gargalo": 2}
        self.assertAlmostEqual(recomendacoes.gerar(inds, dem, cfg, 2012)[0].prioridade, recs[0].prioridade)

    def test_recomendacoes_sem_demanda(self):
        cfg = carregar()
        inds = pd.DataFrame([dict(cod_ibge=1, municipio="Teste", uf="PE", perda_estimada_pct=40,
                                  anomalia_pct=0, classe="alerta")])
        recs = recomendacoes.gerar(inds, demanda.resumo(pedidos_teste().iloc[:0]), cfg, 2026)
        self.assertEqual([r.tipo for r in recs], ["vistoria"])


class TestDecisoes(unittest.TestCase):
    def test_jsonl_auditoria_e_validacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "sub/decisoes.jsonl"
            self.assertEqual(decisoes.listar(arquivo), [])
            registro = dict(id="vistoria-1-2012", tipo="vistoria", municipio="Teste", decisao="aprovada",
                            justificativa="Ação necessária", mensagem="", usuario="gestor")
            decisoes.registrar(registro, arquivo)
            decisoes.registrar({**registro, "decisao": "editada"}, arquivo)
            self.assertEqual(len(decisoes.listar(arquivo)), 2)
            self.assertTrue(decisoes.ja_decidida(registro["id"], arquivo))
            self.assertFalse(decisoes.ja_decidida("outra", arquivo))
            with self.assertRaises(ValueError):
                decisoes.registrar({**registro, "decisao": "paga"}, arquivo)
            self.assertEqual(len(decisoes.listar(arquivo)), 2)

    def test_rascunho_template_rag_e_abstencao(self):
        rec = Mock(municipio="Petrolina", titulo="Convocar 3 agricultores")
        template = decisoes.rascunho_convocacao(rec)
        self.assertIn("CAF", template)
        self.assertIn("a confirmar", template)
        rag = Mock()
        rag.answer.return_value = {"answer": "Leve CPF [1].", "abstained": False}
        self.assertIn("Leve CPF [1].", decisoes.rascunho_convocacao(rec, rag))
        rag.answer.return_value["abstained"] = True
        self.assertEqual(decisoes.rascunho_convocacao(rec, rag), template)
        rag.answer.side_effect = RuntimeError("offline")
        self.assertEqual(decisoes.rascunho_convocacao(rec, rag), template)


if __name__ == "__main__":
    unittest.main()
