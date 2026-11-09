"""Regressões de cache, transação local, selos e apresentação."""
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from email import policy
from email.parser import BytesParser
from providers import config
from pipelines import decisoes, resumo
from formatacao import percentual
import pandas as pd
from pipelines.realidade import recortar_validacao
from ui.graficos import dispersao_validacao, barras_contagens


class TestCorrecoes(unittest.TestCase):
    def test_recorte_e_hover(self):
        quadro = pd.DataFrame([
            dict(municipio="Teste", uf="PE", ano=2012, perda_estimada_pct=12.5, perda_producao_pct=25.5, chuva_mm=100.5),
            dict(municipio="Outro", uf="PB", ano=2012, perda_estimada_pct=50., perda_producao_pct=60., chuva_mm=90.),
            dict(municipio="Teste", uf="PE", ano=2013, perda_estimada_pct=0., perda_producao_pct=0., chuva_mm=200.),
        ])
        placar = recortar_validacao({"dados": quadro}, config.carregar(), {"ufs": ["PE"], "ano": 2012})
        self.assertEqual(placar["pares_validos"], 1)
        figura = dispersao_validacao(placar["dados"], 300)
        self.assertIn("Teste/PE", figura.data[0].text[0])
        self.assertIn("12,5%", figura.data[0].text[0])
        self.assertIn("100,5 mm", figura.data[0].text[0])
        self.assertIsNone(dispersao_validacao(quadro.iloc[:0], 300))
        self.assertIsNone(barras_contagens(pd.DataFrame(), 300))

    def test_guarda_atualizacao_sem_cache_de_efeito_colateral(self):
        from state import dados, store
        estado = {}
        with patch("state.store.obter", side_effect=lambda k, padrao=None: estado.get(k, padrao)), \
                patch("state.store.definir", side_effect=lambda k, v: estado.update({k: v})), \
                patch("state.dados.baixar_clima") as baixar:
            self.assertTrue(dados.atualizar_municipio(2611101, 2012, "teste"))
            self.assertFalse(dados.atualizar_municipio(2611101, 2012, "teste"))
            self.assertTrue(dados.atualizar_municipio(2611101, 2012, "nova"))
            self.assertEqual(baixar.call_count, 2)

    def test_cache_config_copia_e_mtime(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "config.yaml"
            arquivo.write_text("paths: {}\nvalor: [1]\n", encoding="utf-8")
            config._carregar.cache_clear()
            with patch("providers.config.yaml.safe_load", wraps=config.yaml.safe_load) as leitura:
                a = config.carregar(arquivo)
                a["valor"].append(2)
                self.assertEqual(config.carregar(arquivo)["valor"], [1])
                self.assertEqual(leitura.call_count, 1)
                mtime = arquivo.stat().st_mtime_ns
                arquivo.write_text("paths: {}\nvalor: [3]\n", encoding="utf-8")
                os.utime(arquivo, ns=(mtime+1000000000, mtime+1000000000))
                self.assertEqual(config.carregar(arquivo)["valor"], [3])
                self.assertEqual(leitura.call_count, 2)

    def test_decisao_validacao_eml_rollback_e_selo(self):
        with tempfile.TemporaryDirectory() as pasta:
            cfg = {"paths": {"decisoes": Path(pasta)/"log.jsonl", "convocacoes": Path(pasta)/"mensagens"}}
            rec = SimpleNamespace(id="convocacao-123-2012", tipo="convocacao", municipio="Teste", titulo="Convocação")
            for escolha, motivo, mensagem, usuario in [("invalida", "", "texto", "gestor"), ("aprovada", "", "texto", ""), ("rejeitada", "", "", "gestor"), ("aprovada", "", "", "gestor")]:
                with self.assertRaises(ValueError):
                    decisoes.salvar_decisao(rec, escolha, motivo, mensagem, usuario, cfg)
            with patch("pipelines.decisoes.registrar", side_effect=OSError("disco")):
                with self.assertRaises(OSError):
                    decisoes.salvar_decisao(rec, "aprovada", "Revisado", "Texto", "gestor", cfg)
            self.assertEqual(list(cfg["paths"]["convocacoes"].glob("*.eml")), [])
            registro = decisoes.salvar_decisao(rec, "aprovada", "Revisado", "Texto", "gestor", cfg)
            eml = BytesParser(policy=policy.default).parsebytes(next(cfg["paths"]["convocacoes"].glob("*.eml")).read_bytes())
            self.assertEqual(eml["X-Unsent"], "1")
            self.assertIsNone(eml["To"])
            self.assertEqual(eml.get_content().strip(), "Texto")
            selo = decisoes.selos(decisoes.listar(cfg["paths"]["decisoes"]))[rec.id]
            self.assertEqual(selo, registro)
            self.assertEqual(selo["usuario"], "gestor")
            self.assertTrue(selo["quando"])
            with self.assertRaises(ValueError):
                decisoes.salvar_decisao(rec, "aprovada", "", "Texto", "gestor", cfg)

    def test_resumo_virgula_e_verificador(self):
        fatos = dict(safra=2012, data_corte="30/06/2012", estimavel=True,
                     municipios_por_classe={"seguros": 2}, acoes_pendentes={},
                     travados_sem_caf={"total": 0, "simulado": True},
                     decisoes_ultimos_7_dias={"aprovadas": 0, "ajustadas": 0, "recusadas": 0},
                     realidade={"mediana_perda_real_pct": 0.0})
        texto = resumo.template(fatos)
        self.assertIn("0,0%", texto)
        self.assertEqual(resumo.numeros_desconhecidos(texto, fatos), [])
        self.assertEqual(resumo.fatos_exibicao(fatos)["realidade"]["mediana_perda_real_pct"], "0,0")
        self.assertEqual(percentual(12.5), "12,5%")
