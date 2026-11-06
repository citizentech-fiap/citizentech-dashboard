"""Resumo e integração LLM offline, com fatos do painel e clientes simulados."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from pipelines import resumo
from providers import genai
from providers.config import carregar


class TestResumo(unittest.TestCase):
    def setUp(self):
        self.cfg = carregar()
        self.ind = pd.DataFrame([dict(cod_ibge=1, municipio="Teste", classe="critico",
            estimavel=False, perda_estimada_pct=float('nan'), anomalia_pct=-47.2)])
        self.dem = pd.DataFrame([dict(travados_sem_caf=12)])

    def fatos(self, ano=2026):
        return resumo.fatos(self.ind, self.dem, [], [], self.cfg, ano, f"{ano}-01-31",
            pd.DataFrame([dict(cod_ibge=1, ano=2025, perda_producao_pct=62.5)]))

    def test_fatos_simulados_sem_futuro(self):
        fatos = self.fatos()
        self.assertFalse(fatos['estimavel'])
        self.assertEqual(fatos['travados_sem_caf'], dict(total=12, simulado=True))
        self.assertNotIn('realidade', fatos)
        self.assertIn('anomalia_pct', fatos['top_criticos'][0])
        self.assertEqual(self.fatos(2025)['realidade']['mediana_perda_real_pct'], 62.5)

    def test_numeros_e_template(self):
        fatos = self.fatos()
        self.assertEqual(resumo.numeros_desconhecidos('Safra 2026, corte 31/01/2026, 47,2% e 12 pedidos.', fatos), [])
        self.assertTrue(resumo.numeros_desconhecidos('987654321 famílias', fatos))
        self.assertEqual(resumo.numeros('1.234,5%'), resumo.numeros('1234.5'))
        texto = resumo.template(fatos)
        self.assertIn('simulado', texto)
        self.assertIn('Próximas ações', texto)
        self.assertEqual(resumo.numeros_desconhecidos(texto, fatos), [])
        self.assertNotRegex(texto, r'\b(?:nan|NaN|None)\b')

    def test_pendencias_e_decisoes_da_ultima_semana(self):
        agora = datetime.now(timezone.utc)
        historico = [dict(id='vistoria-1-2026', municipio='Teste', decisao='editada', quando=agora.isoformat()),
                     dict(id='vistoria-2-2026', municipio='Teste', decisao='aprovada',
                          quando=(agora - timedelta(days=8)).isoformat()),
                     dict(id='vistoria-3-2025', municipio='Teste', decisao='rejeitada', quando=agora.isoformat())]
        recs = [SimpleNamespace(id='vistoria-1-2026', tipo='vistoria'),
                SimpleNamespace(id='mutirao_caf-1-2026', tipo='mutirao_caf')]
        fatos = resumo.fatos(self.ind, self.dem, recs, historico, self.cfg, 2026, '2026-01-31')
        self.assertEqual(fatos['acoes_pendentes'], {'Mutirão do CAF': 1})
        self.assertEqual(fatos['decisoes_ultimos_7_dias'], dict(aprovadas=0, ajustadas=1, recusadas=0))

    def test_geracao_stub_sem_chave_e_erro(self):
        pasta = str(self.cfg['paths']['genai_path'])
        sys.path.insert(0, pasta)
        self.addCleanup(sys.path.remove, pasta)
        from citizen_rag.llm import StubLLM, UnavailableLLM
        stub = StubLLM('Resumo da safra 2026.')
        with patch('citizen_rag.llm.make_llm', return_value=stub) as criar:
            self.assertEqual(genai.gerar_texto('sistema', 'fatos'), ('Resumo da safra 2026.', ''))
            self.assertTrue(criar.call_args.args[0]['llm']['cache'])
        with patch('citizen_rag.llm.make_llm', return_value=UnavailableLLM()):
            texto, motivo = genai.gerar_texto('sistema', 'fatos')
            self.assertIsNone(texto)
            self.assertTrue(motivo)
        with patch('citizen_rag.llm.make_llm', side_effect=OSError('offline')):
            self.assertIsNone(genai.gerar_texto('sistema', 'fatos')[0])

    def test_selo_so_para_simulacao(self):
        from ui.componentes import selo_simulado
        with patch('providers.config.carregar', return_value=self.cfg), patch('ui.componentes.st.html') as html:
            selo_simulado()
            self.assertIn('simulado', html.call_args.args[0])
            self.assertIn('LGPD', html.call_args.args[0])
            html.reset_mock()
            self.cfg['fontes']['pedidos'] = 'rpa'
            selo_simulado()
            html.assert_not_called()
