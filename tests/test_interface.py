"""Fumaça e decisões reais em saídas temporárias, sem rede ou envio."""
from datetime import date
from email import policy
from email.parser import BytesParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from threading import RLock

import streamlit as st
from streamlit.testing.v1 import AppTest

from pipelines import decisoes
from providers.config import RAIZ, carregar
from state import dados, store
from ui.graficos import grafico_chuva
from ui.acoes import sugestao


class TestInterface(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = carregar()
        self.cfg["paths"]["decisoes"] = Path(self.temp.name) / "decisoes.jsonl"
        self.cfg["paths"]["convocacoes"] = Path(self.temp.name) / "convocacoes"
        self.patches = [patch("state.dados.CFG", self.cfg),
                        patch("pipelines.decisoes.carregar", return_value=self.cfg),
                        patch("state.dados.recurso_rag", return_value=(None, "RAG indisponível; template local.", RLock()))]
        for recurso in self.patches:
            recurso.start()
            self.addCleanup(recurso.stop)
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)

    def app(self):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
        self.sem_excecoes(app)
        app.text_input(key="gestor").set_value("gestor-teste").run()
        return app

    def sem_excecoes(self, app):
        self.assertEqual([e.message for e in app.exception], [])

    def aba(self, app, indice):
        # AppTest ainda representa tabs como Block, sem select(). O valor é
        # a mesma chave do controle real on_change='rerun' do Streamlit.
        app.session_state["aba"] = store.ABAS[indice]
        app.run()
        self.sem_excecoes(app)

    def registros(self):
        return decisoes.listar(self.cfg["paths"]["decisoes"])

    def test_gestor_obrigatorio_e_selo(self):
        app = self.app()
        app.text_input(key="gestor").set_value("").run()
        self.aba(app, 2)
        botoes = [b for b in app.button if (b.key or "").startswith("aprovar_")]
        self.assertTrue(botoes)
        self.assertTrue(all(b.disabled for b in botoes))
        chave = botoes[0].key
        app.text_input(key="gestor").set_value("EMATER-teste").run()
        app.button(key=chave).click().run()
        self.sem_excecoes(app)
        self.assertTrue(any("Aprovada · EMATER-teste" in e.value for e in app.success))
        self.assertFalse(any(b.key == chave for b in app.button))

    def test_sem_repositorios_vizinhos(self):
        from providers import genai
        cfg = carregar()
        cfg["fontes"]["pedidos"] = "rpa"
        for chave in ("rpa_controle", "genai_path"):
            cfg["paths"][chave] = Path(self.temp.name) / "ausente" / chave
        with patch("state.dados.CFG", cfg), patch("providers.rpa.carregar", return_value=cfg), \
                patch("providers.genai.carregar", return_value=cfg), \
                patch("providers.genai.import_module", side_effect=ModuleNotFoundError("ausente")):
            app = self.app()
            self.assertTrue(any("sintéticos" in w.value for w in app.warning))
            for indice in (1, 2, 3):
                self.aba(app, indice)
            app.button(key="gerar_resumo").click().run()
            self.sem_excecoes(app)
            self.assertTrue(any("sem IA" in c.value for c in app.caption))
            self.assertIsNone(genai.criar_rag()[0])

    def test_percurso_filtros_replay_e_evidencias(self):
        app = self.app()
        self.assertEqual(app.selectbox(key="ano").value, self.cfg["safra"]["ano_demo_seca"])
        self.assertEqual([t.label for t in app.tabs], list(store.ABAS))
        self.assertEqual(app.tabs[3].label, "Resumo da semana")
        self.assertEqual(app.title[0].value, "Onde agir primeiro?")
        self.assertTrue(any("seca histórica, modo demonstração" in c.value for c in app.markdown))
        self.assertTrue(any("Veja onde a seca está pior" in c.value for c in app.caption))
        self.assertFalse(next(e for e in app.expander if e.label == "Ajustes avançados").proto.expanded)
        self.assertFalse(next(e for e in app.expander if e.label == "Como calculamos").proto.expanded)
        self.assertEqual(len(app.get("plotly_chart")), 5)
        app.slider(key="mes").set_value(3).run()
        self.assertTrue(any("31/03/2012" in c.value for c in app.caption))
        app.multiselect(key="ufs").set_value(["PE"])
        app.selectbox(key="cultura").set_value("feijao")
        app.selectbox(key="servico").set_value("pronaf")
        app.slider(key="limiar").set_value(60).run()
        self.sem_excecoes(app)
        chave = next(b.key for b in app.button if (b.key or "").startswith("panorama_abrir_"))
        codigo = int(chave.rsplit("_", 1)[1])
        app.button(key=chave).click().run()
        self.sem_excecoes(app)
        self.assertEqual(app.selectbox(key="_municipio").value, codigo)
        self.assertEqual(len(app.tabs[1].get("image")), 1)  # Calendário Matplotlib renderizado.
        self.assertTrue(any("O que fazer em " in h.value for h in app.subheader))
        self.aba(app, 2)
        self.sem_excecoes(app)
        self.assertTrue(any("ações aguardando sua decisão" in h.value for h in app.subheader))
        self.aba(app, 3)
        self.assertTrue(any("serviço pronaf" in c.value for c in app.caption))
        self.aba(app, 0)
        self.assertEqual(app.slider(key="mes").value, 3)
        self.assertEqual(app.multiselect(key="ufs").value, ["PE"])

    def test_convocacao_exige_revisao_e_salva_edicao(self):
        app = self.app()
        self.aba(app, 2)
        id_rec = next(b.key.removeprefix("aprovar_") for b in app.button
                      if (b.key or "").startswith("aprovar_convocacao"))
        app.button(key=f"aprovar_{id_rec}").click().run()
        self.sem_excecoes(app)
        self.assertEqual(self.registros(), [])
        self.assertFalse(self.cfg["paths"]["convocacoes"].exists())
        self.assertIn("Sede da EMATER", app.text_area(key=f"mensagem_{id_rec}").value)
        app.button(key=f"confirmar_{id_rec}").click().run()
        self.assertTrue(any("marque a confirmação" in e.value for e in app.error))
        app.button(key=f"voltar_{id_rec}").click().run()
        self.assertIsNotNone(app.date_input(key=f"data_{id_rec}").value)
        self.assertTrue(app.text_area(key=f"plano_{id_rec}").value)
        app.date_input(key=f"data_{id_rec}").set_value(date.today())
        app.text_input(key=f"local_{id_rec}").set_value("EMATER municipal, às 9h")
        app.text_area(key=f"plano_{id_rec}").set_value("Atender em grupos pequenos, com prioridade às pendências.")
        app.button(key=f"salvar_ajuste_{id_rec}").click().run()
        self.sem_excecoes(app)
        self.assertEqual(self.registros(), [])
        self.assertFalse(self.cfg["paths"]["convocacoes"].exists())
        self.assertIn("EMATER municipal", app.text_area(key=f"mensagem_{id_rec}").value)
        app.button(key=f"voltar_{id_rec}").click().run()
        self.sem_excecoes(app)
        self.assertEqual(app.date_input(key=f"data_{id_rec}").value, date.today())
        self.assertEqual(app.text_input(key=f"local_{id_rec}").value, "EMATER municipal, às 9h")
        app.button(key=f"salvar_ajuste_{id_rec}").click().run()
        app.button(key=f"confirmar_{id_rec}").click().run()
        self.assertTrue(any("marque a confirmação" in e.value for e in app.error))
        self.assertEqual(self.registros(), [])
        app.checkbox(key=f"revisada_{id_rec}").set_value(True)
        app.button(key=f"confirmar_{id_rec}").click().run()
        self.sem_excecoes(app)
        registros = self.registros()
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["decisao"], "editada")
        self.assertFalse(any(b.key == f"aprovar_{id_rec}" for b in app.button))
        self.assertEqual(len(app.dataframe[0].value), 1)
        arquivo = self.cfg["paths"]["convocacoes"] / f"{id_rec}.eml"
        mensagem = BytesParser(policy=policy.default).parsebytes(arquivo.read_bytes())
        self.assertEqual(mensagem["X-Unsent"], "1")
        self.assertIsNone(mensagem["To"])
        self.assertIn("EMATER municipal", mensagem.get_content())
        self.assertIn("CAF", mensagem.get_content())
        self.aba(app, 0)
        self.aba(app, 2)
        self.assertFalse(any(b.key == f"aprovar_{id_rec}" for b in app.button))

    def test_recusa_sem_motivo_bloqueada(self):
        app = self.app()
        self.aba(app, 2)
        id_rec = next(b.key.removeprefix("recusar_") for b in app.button if (b.key or "").startswith("recusar_vistoria"))
        app.button(key=f"recusar_{id_rec}").click().run()
        app.button(key=f"confirmar_recusa_{id_rec}").click().run()
        self.assertTrue(any("motivo é obrigatório" in e.value for e in app.error))
        self.assertEqual(self.registros(), [])
        app.text_area(key=f"motivo_{id_rec}").set_value("Vistoria já realizada pela equipe municipal.")
        app.button(key=f"confirmar_recusa_{id_rec}").click().run()
        self.sem_excecoes(app)
        self.assertEqual(self.registros()[0]["decisao"], "rejeitada")
        self.assertFalse(any(b.key == f"aprovar_{id_rec}" for b in app.button))

    def test_jornada_dois_cliques_aprova_vistoria_e_audita(self):
        app = self.app()
        primeiro = next(b for b in app.button if b.label == "Ver por quê →")
        codigo = int(primeiro.key.rsplit("_", 1)[1])
        primeiro.click().run()  # clique 1: abre a aba 2 no município escolhido
        self.sem_excecoes(app)
        self.assertEqual(app.session_state["aba"], store.ABAS[1])
        self.assertEqual(app.selectbox(key="_municipio").value, codigo)
        id_rec = f"vistoria-{codigo}-2012"
        self.assertEqual(len(app.date_input), 0)  # aprovação não exige preencher campos
        app.button(key=f"aprovar_{id_rec}").click().run()  # clique 2: decide
        self.sem_excecoes(app)
        self.assertEqual(len(self.registros()), 1)
        registro = self.registros()[0]
        self.assertEqual(registro["id"], id_rec)
        self.assertEqual(registro["decisao"], "aprovada")
        self.assertEqual(registro["usuario"], "gestor-teste")
        self.assertIn("Sede da EMATER", registro["mensagem"])
        self.assertIn("Plano:", registro["mensagem"])
        self.assertEqual(len(self.cfg["paths"]["decisoes"].read_text(encoding="utf-8").splitlines()), 1)
        self.assertFalse(any(b.key == f"aprovar_{id_rec}" for b in app.button))
        self.assertEqual(len(app.get("toast")), 1)
        self.assertFalse(self.cfg["paths"]["convocacoes"].exists())
        self.aba(app, 2)
        self.assertFalse(any(b.key == f"aprovar_{id_rec}" for b in app.button))
        self.assertEqual(len(app.dataframe[0].value), 1)
        self.assertFalse(next(e for e in app.expander if e.label == "Decisões já tomadas").proto.expanded)

    def test_ajustar_mantem_sugestao_e_registra_edicao(self):
        app = self.app()
        self.aba(app, 2)
        id_rec = next(b.key.removeprefix("ajustar_") for b in app.button if (b.key or "").startswith("ajustar_vistoria"))
        app.button(key=f"ajustar_{id_rec}").click().run()
        sugerida = app.date_input(key=f"data_{id_rec}").value
        self.assertEqual(sugerida.weekday(), 0)
        self.assertGreaterEqual(sugerida, date.today())
        self.assertTrue(app.text_input(key=f"local_{id_rec}").value.startswith("Sede da EMATER de "))
        self.assertTrue(app.text_area(key=f"plano_{id_rec}").value)
        app.run()
        self.assertEqual(app.date_input(key=f"data_{id_rec}").value, sugerida)
        app.text_input(key=f"local_{id_rec}").set_value("Unidade municipal, às 8h")
        app.button(key=f"salvar_ajuste_{id_rec}").click().run()
        self.sem_excecoes(app)
        self.assertEqual(self.registros()[0]["decisao"], "editada")
        self.assertIn("Unidade municipal", self.registros()[0]["mensagem"])

    def test_sugestao_proxima_segunda_inclui_hoje(self):
        rec = Mock(municipio="Salgueiro", acao_sugerida="Solicitar vistoria.")
        for hoje in (date(2026, 11, 5), date(2026, 11, 8), date(2026, 11, 9)):
            with self.subTest(hoje=hoje), patch("ui.acoes.date") as calendario:
                calendario.today.return_value = hoje
                self.assertEqual(sugestao(rec, self.cfg)["data"], date(2026, 11, 9))

    def test_fila_cinco_mais_cinco_e_contador(self):
        app = self.app()
        self.aba(app, 2)
        quantidade = len(dados.contexto(2012, "milho", tuple(app.multiselect(key="ufs").value),
                                       "todos", 40, dados.versao_snapshots())["recomendacoes"])
        self.assertEqual(sum((b.key or "").startswith("aprovar_") for b in app.button), 5)
        self.assertFalse(any(s.label == "Página de recomendações" for s in app.selectbox))
        self.assertTrue(any(t.key == "gestor" for t in app.text_input))
        app.button(key="mostrar_mais").click().run()
        self.assertEqual(sum((b.key or "").startswith("aprovar_") for b in app.button), 10)
        id_rec = next(b.key.removeprefix("aprovar_") for b in app.button if (b.key or "").startswith("aprovar_vistoria"))
        app.button(key=f"aprovar_{id_rec}").click().run()
        self.assertTrue(app.subheader[0].value.startswith(f"{quantidade - 1} ações"))
        app.selectbox(key="ano").set_value(2013).run()
        self.assertEqual(sum((b.key or "").startswith("aprovar_") for b in app.button), 5)

    def test_safra_sem_perda_e_recorte_vazio_sao_estados_validos(self):
        app = self.app()
        app.selectbox(key="ano").set_value(2024).run()  # ERA5: nenhum município com perda estimada >= 40%
        self.assertTrue(any("nenhum município precisa de vistoria" in m.value for m in app.markdown))
        self.aba(app, 2)
        self.assertTrue(any("Nenhum município atingiu o critério de 40% nesta safra" in s.value for s in app.success))
        self.assertFalse(any((b.key or "").startswith("aprovar_vistoria") for b in app.button))
        self.assertGreater(sum((b.key or "").startswith("aprovar_mutirao") for b in app.button), 0)
        app.selectbox(key="ano").set_value(2013).run()
        self.sem_excecoes(app)
        app.multiselect(key="ufs").set_value([]).run()
        self.sem_excecoes(app)
        self.assertTrue(any("Escolha ao menos uma UF" in i.value for i in app.info))

    def test_api_falha_preserva_snapshot_e_avisa(self):
        arquivo = self.cfg["paths"]["clima_diario"]
        antes = arquivo.read_bytes()
        app = self.app()
        app.multiselect(key="ufs").set_value(["SE"]).run()
        with patch("providers.atualizacao_clima.open_meteo.diario", side_effect=OSError("offline")) as diario:
            next(b for b in app.button if b.label == "Atualizar dados do Open-Meteo").click().run()
        self.sem_excecoes(app)
        diario.assert_called_once()
        self.assertEqual(arquivo.read_bytes(), antes)
        self.assertTrue(any("últimos dados locais" in w.value for w in app.warning))

    def test_resumo_template_cache_e_guardrail(self):
        app = self.app()
        self.aba(app, 3)
        with patch("providers.genai.gerar_texto", return_value=(None, "Sem IA")) as gerar:
            app.button(key="gerar_resumo").click().run()
            self.sem_excecoes(app)
            self.assertTrue(app.text_area[0].value.startswith("Safra 2012"))
            self.assertTrue(any("Resumo automático sem IA" in c.value for c in app.caption))
            app.button(key="gerar_resumo").click().run()
            gerar.assert_called_once()
        app.text_area[0].set_value("Há 987654321 famílias.").run()
        self.assertTrue(any("Números fora dos fatos" in w.value for w in app.warning))
        app.button(key="template_resumo").click().run()
        self.assertNotIn("987654321", app.text_area[0].value)
        app.selectbox(key="servico").set_value("pronaf").run()
        with patch("providers.genai.gerar_texto", return_value=("Há 987654321 famílias.", "")):
            app.button(key="gerar_resumo").click().run()
        self.assertTrue(any("Números fora dos fatos" in w.value for w in app.warning))
        self.assertTrue(any("Gerado por IA" in c.value for c in app.caption))

    def test_replay_janeiro_sem_valores_ausentes_e_selos(self):
        app = self.app()
        self.assertTrue(any("Perda real (IBGE)" in e.proto.body for e in app.get("html")))
        self.assertTrue(any("simulado" in e.proto.body for e in app.get("html")))
        app.selectbox(key="ano").set_value(2026).run()
        app.slider(key="mes").set_value(1).run()
        self.sem_excecoes(app)
        textos = [e.value for tipo in (app.markdown, app.caption, app.warning, app.info) for e in tipo]
        textos += [e.proto.body for e in app.get("html")]
        for texto in textos:
            self.assertNotRegex(texto, r"\b(?:nan|NaN|None)\b")
        self.assertTrue(any("Cedo para estimar perda" in t for t in textos))
        tabela = app.dataframe[0].value
        self.assertFalse(tabela.isna().any().any())

    def test_ausencia_de_snapshots_e_eixo_do_criterio(self):
        with patch("state.dados.dados_locais.malhas", side_effect=FileNotFoundError), \
                patch("state.dados.rpa.pedidos", side_effect=FileNotFoundError):
            app = self.app()
        self.assertTrue(any("Pedidos indisponíveis" in w.value for w in app.warning))
        self.assertTrue(any("Mapa indisponível" in w.value for w in app.warning))
        dados.indicadores.clear()
        dados.contexto.clear()
        with patch("state.dados.risco.indicadores", side_effect=ValueError("Clima incompleto")):
            app.run()
        self.sem_excecoes(app)
        self.assertTrue(any("Clima incompleto" in w.value for w in app.warning))
        versao = dados.versao_snapshots()
        serie = dados.serie(2611101, 2012, versao)
        ev = dados.evolucao(2012, "milho", versao).query("cod_ibge == 2611101")
        figura = grafico_chuva(serie, 400, cfg=self.cfg, cultura="milho", limiar=40, evolucao=ev)
        self.assertEqual(figura.layout.yaxis.title.text, "Acumulado (mm)")
        self.assertEqual(figura.layout.yaxis2.title.text, "Perda estimada (%)")
        self.assertEqual(figura.layout.shapes[0].yref, "y2")

    def test_cache_evitar_recalculo_em_rerun_e_mudar_com_cultura(self):
        with patch("state.dados.risco.indicadores", wraps=dados.risco.indicadores) as indicadores:
            app = self.app()
            chamadas = indicadores.call_count
            self.assertGreater(chamadas, 0)
            app.run()
            self.assertEqual(indicadores.call_count, chamadas)
            app.slider(key="limiar").set_value(60).run()
            self.assertEqual(indicadores.call_count, chamadas)
            app.selectbox(key="cultura").set_value("feijao").run()
            self.assertGreater(indicadores.call_count, chamadas)
            self.sem_excecoes(app)

    def test_gravacao_recupera_falha_e_impede_duplicidade(self):
        ctx = dados.contexto(2012, "milho", ("PE",), "todos", 40, dados.versao_snapshots())
        rec = next(r for r in ctx["recomendacoes"] if r.tipo == "convocacao")
        with patch("state.dados.decisoes.registrar", side_effect=OSError("disco indisponível")):
            with self.assertRaises(OSError):
                dados.salvar_decisao(rec, "aprovada", "Revisado", "Texto revisado", "gestor-demo")
        self.assertEqual(self.registros(), [])
        self.assertEqual(list(self.cfg["paths"]["convocacoes"].glob("*.eml")), [])
        dados.salvar_decisao(rec, "aprovada", "Revisado", "Texto revisado", "gestor-demo")
        with self.assertRaisesRegex(ValueError, "já foi decidida"):
            dados.salvar_decisao(rec, "aprovada", "Revisado", "Texto duplicado", "gestor-demo")
        self.assertEqual(len(self.registros()), 1)
        self.assertEqual(len(list(self.cfg["paths"]["convocacoes"].glob("*.eml"))), 1)


if __name__ == "__main__":
    unittest.main()
