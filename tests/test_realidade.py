"""PAM, pagamentos e validação com fontes falsas; nenhum acesso à rede."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pandas as pd
import requests

from pipelines import realidade, recomendacoes, risco
from providers import ibge_pam, transparencia
from providers.config import carregar
from scripts import preparar_dados


def zip_sintetico(mes="201305", nome="Ouricuri", uf="PE", nis="FALSO-001", valor="140,00"):
    saida = io.BytesIO()
    cab = '"MÊS REFERÊNCIA";"UF";"CÓDIGO MUNICÍPIO SIAFI";"NOME MUNICÍPIO";"NIS FAVORECIDO";"NOME FAVORECIDO";"VALOR PARCELA"\n'
    texto = cab + f'{mes};{uf};0000;{nome};{nis};PESSOA FICTÍCIA;{valor}\n' * 2
    texto += f'{mes};XX;0000;Fora do recorte;FALSO-999;NOME FICTÍCIO;999,00\n'
    with zipfile.ZipFile(saida, "w") as z:
        z.writestr("sintetico.csv", texto.encode("latin-1"))
    return saida.getvalue()


class TestPAM(unittest.TestCase):
    @patch("providers.ibge_pam.http.get")
    def test_parser_sidra_nan_e_variaveis(self, get):
        dados = [{"D1C": "Município (Código)"}]
        for cultura in ("2711", "2702"):
            for variavel, valor in zip(("109", "216", "214"), ("13000", "130", "4") if cultura == "2711" else ("-", "...", "X")):
                dados.append(dict(D1C="2609907", D2C=variavel, D3C="2012", D4C=cultura, V=valor))
        get.return_value = json.dumps(dados).encode()
        q = ibge_pam.producao([2609907], [2012]).set_index("cultura")
        self.assertEqual(q.loc["milho", "producao_t"], 4)
        self.assertEqual(q.loc["milho", "area_plantada_ha"], 13000)
        self.assertEqual(q.loc["feijao", "area_plantada_ha"], 0)  # "-" = zero absoluto no IBGE
        self.assertTrue(q.loc["feijao", ["area_colhida_ha", "producao_t"]].isna().all())  # "..." e "X"
        self.assertIn("/v/109,216,214/p/2012/c81/2711,2702", get.call_args.args[0])
        with self.assertRaisesRegex(ValueError, "variáveis ausentes"):
            ibge_pam.parsear(dados[:-1])


class TestTransparencia(unittest.TestCase):
    def setUp(self):
        self.municipios = pd.DataFrame([dict(cod_ibge=2609907, municipio="Ouricuri", uf="PE")])

    def test_agregacao_zip_privacidade_e_familias_distintas_na_safra(self):
        q = transparencia.agregar_zips([("201305", zip_sintetico()),
                                       ("201306", zip_sintetico("201306"))], self.municipios)
        self.assertEqual(list(q), transparencia.COLUNAS)
        self.assertEqual(q.familias.tolist(), [1])
        self.assertEqual(q.valor_total.tolist(), [560])
        self.assertEqual(q.meses_com_pagamento.tolist(), [2])
        self.assertEqual(q.safra.tolist(), [2012])
        self.assertNotIn("FALSO", q.to_csv(index=False))
        self.assertNotIn("FICT", q.to_csv(index=False))
        self.assertEqual(q.attrs, {})
        self.assertEqual(transparencia.safra_pagamento("201307"), 2013)
        self.assertEqual(transparencia.normalizar("  São  Raimundo Nónato "), "SAO RAIMUNDO NONATO")

    @patch("providers.transparencia.time.sleep")
    @patch("providers.transparencia.http.get")
    def test_download_sem_cache_e_mes_inexistente(self, get, sleep):
        resposta = requests.Response()
        resposta.status_code = 404
        get.side_effect = [requests.HTTPError(response=resposta), zip_sintetico()]
        q = transparencia.garantia_safra(["201304", "201305"], self.municipios)
        self.assertEqual(q.attrs["cobertura"], {"201304": "inexistente", "201305": "disponivel"})
        self.assertTrue(all(c.kwargs["cache"] is False for c in get.call_args_list))

    def test_referencia_incorreta_rejeitada(self):
        with self.assertRaisesRegex(ValueError, "referência"):
            transparencia.agregar_zips([("201306", zip_sintetico())], self.municipios)

    @patch("providers.transparencia.time.sleep")
    @patch("providers.transparencia.http.get")
    def test_405_tem_pausa_e_retry_403_nao_vira_mes_inexistente(self, get, sleep):
        resposta = requests.Response()
        resposta.status_code = 405
        get.side_effect = [requests.HTTPError(response=resposta), zip_sintetico()]
        q = transparencia.garantia_safra("201305", self.municipios)
        self.assertEqual(q.familias.tolist(), [1])
        self.assertIn(carregar()["fontes"]["backoff_download_s"], [c.args[0] for c in sleep.call_args_list])
        resposta.status_code = 403
        get.side_effect = requests.HTTPError(response=resposta)
        with self.assertRaises(requests.RequestException):
            transparencia.garantia_safra("201305", self.municipios)

    @patch("scripts.preparar_dados.transparencia.meses_publicados", return_value={"201305"})
    @patch("scripts.preparar_dados.transparencia.garantia_safra")
    def test_idempotencia_snapshot_e_cobertura(self, get, publicados):
        cfg = carregar()
        with tempfile.TemporaryDirectory() as pasta:
            cfg["paths"]["garantia_safra"] = Path(pasta) / "agregado.csv"
            cfg["paths"]["garantia_safra_cobertura"] = Path(pasta) / "cobertura.json"
            cfg["fontes"].update(pagamentos_inicio="2013-05", pagamentos_fim="2013-06")
            q = transparencia.agregar_zips([("201305", zip_sintetico())], self.municipios)
            q.attrs["cobertura"] = {"201305": "disponivel", "201306": "inexistente"}
            get.return_value = q
            preparar_dados.baixar_garantia_safra(self.municipios, cfg)
            preparar_dados.baixar_garantia_safra(self.municipios, cfg)
            get.assert_called_once()
            self.assertEqual(len(list(Path(pasta).iterdir())), 2)
            self.assertNotIn("FALSO", cfg["paths"]["garantia_safra"].read_text(encoding="utf-8"))


class TestRealidade(unittest.TestCase):
    def serie(self):
        return pd.DataFrame([dict(cod_ibge=1, ano=a, cultura="milho", area_plantada_ha=100,
                                  area_colhida_ha=60, producao_t=50 if a == 2012 else 100)
                             for a in range(2002, 2013)])

    def test_media_dez_anos_sem_futuro_lacuna_zero_e_clip(self):
        q = self.serie()
        r = realidade.perda_real("milho", q).iloc[-1]
        self.assertEqual(r.perda_producao_pct, 50)
        self.assertEqual(r.perda_area_pct, 40)
        futuro = q.iloc[[-1]].assign(ano=2013, producao_t=1000000)
        com_futuro = realidade.perda_real("milho", pd.concat([q, futuro], ignore_index=True))
        self.assertEqual(com_futuro.loc[com_futuro.ano.eq(2012), "perda_producao_pct"].iloc[0], 50)
        self.assertTrue(pd.isna(realidade.perda_real("milho", q.iloc[1:]).iloc[-1].perda_producao_pct))
        self.assertTrue(pd.isna(realidade.perda_real("milho", q.assign(producao_t=0)).iloc[-1].perda_producao_pct))
        q.loc[q.ano.eq(2012), "producao_t"] = 1000
        self.assertEqual(realidade.perda_real("milho", q).iloc[-1].perda_producao_pct, 0)
        q.loc[q.ano.eq(2012), "area_plantada_ha"] = 0
        self.assertTrue(pd.isna(realidade.perda_real("milho", q).iloc[-1].perda_area_pct))

    @patch("pipelines.realidade._cobertura_pagamentos", return_value=False)
    @patch("pipelines.realidade.pagamentos")
    @patch("pipelines.realidade.perda_real")
    @patch("pipelines.realidade.risco.indicadores")
    def test_validacao_matriz_exclusao_e_sem_pagamento_desconhecido(self, inds, reais, pagos, cobertura):
        cfg = carregar()
        cfg["safra"]["anos_disponiveis"] = [2012]
        inds.return_value = pd.DataFrame(dict(cod_ibge=[1, 2, 3, 4, 5], municipio=list("ABCDE"),
                                              uf="PE", perda_estimada_pct=[0, 80, 20, 90, 70]))
        reais.return_value = pd.DataFrame(dict(cod_ibge=[1, 2, 3, 4, 5], ano=2012,
                                               perda_producao_pct=[0, 90, 80, 10, float("nan")], perda_area_pct=0))
        pagos.return_value = pd.DataFrame(dict(cod_ibge=[2], safra=[2012], familias=[10],
                                               valor_total=[1000], meses_com_pagamento=[1]))
        with patch("pipelines.realidade.carregar", return_value=cfg):
            r = realidade.validacao("milho")
        self.assertEqual(r["matriz"].to_numpy().tolist(), [[1, 1], [1, 1]])
        self.assertEqual(r["acuracia"], .5)
        self.assertEqual(r["pares_excluidos"], 1)
        self.assertEqual(r["divergencias"].cod_ibge.iloc[0], 4)
        self.assertTrue(r["dados"].loc[r["dados"].cod_ibge.eq(2), "pagou_garantia_safra"].iloc[0])
        self.assertTrue(pd.isna(r["dados"].pagou_garantia_safra.iloc[0]))


class TestReplay(unittest.TestCase):
    def test_snapshots_janeiro_junho_2026_e_marco_2012(self):
        janeiro = risco.indicadores(2026, "milho", "2026-01-31")
        self.assertEqual(len(janeiro), 23)
        self.assertFalse(janeiro.estimavel.any())
        self.assertTrue(janeiro.perda_estimada_pct.isna().all())
        self.assertEqual(janeiro.classe.tolist(), [risco.classificar_chuva(a, carregar())
                                                  for a in janeiro.anomalia_pct])
        junho = risco.indicadores(2026, "milho", "2026-06-30")
        self.assertTrue(junho.estimavel.all())
        # Snapshot ERA5: safra 2026 regular na maior parte (5/23 com perda >= 40%), longe de 2012.
        self.assertLessEqual(junho.perda_estimada_pct.ge(40).sum(), 5)
        marco = risco.indicadores(2012, "milho", "2012-03-31")
        self.assertTrue(marco.estimavel.all())
        self.assertTrue(marco.perda_estimada_pct.notna().all())
        self.assertEqual(marco.perda_estimada_pct.ge(40).sum(), 23)
        # Limites originais de perda: crítico >=60, alerta >=40.
        self.assertEqual(marco.classe.eq("critico").sum(), 18)

    def test_limites_chuva(self):
        for n, classe in [(5, "seguro"), (0, "seguro"), (-.1, "atencao"), (-20, "atencao"),
                          (-20.1, "alerta"), (-40, "alerta"), (-40.1, "critico")]:
            self.assertEqual(risco.classificar_chuva(n, carregar()), classe)

    def test_vistoria_bloqueada_mantem_demais_regras_e_score_finito(self):
        inds = pd.DataFrame([dict(cod_ibge=1, municipio="Teste", uf="PE", estimavel=False,
                                  perda_estimada_pct=float("nan"), anomalia_pct=-50, classe="critico")])
        dem = pd.DataFrame([dict(cod_ibge=1, familias_garantia_safra=20, travados_sem_caf=10, docs_completos=5)])
        recs = recomendacoes.gerar(inds, dem, carregar(), 2026)
        self.assertEqual({r.tipo for r in recs}, {"mutirao_caf", "convocacao"})
        self.assertTrue(all(r.prioridade == .5 for r in recs))
        self.assertTrue(all("nan" not in r.justificativa for r in recs))


if __name__ == "__main__":
    unittest.main()
