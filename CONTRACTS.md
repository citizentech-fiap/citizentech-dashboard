# Contratos de dados do Mandacaru

## Entradas (snapshots em `data/`, gerados por `scripts/preparar_dados.py`)
- `municipios_semiarido.csv`: `municipio, uf, cod_ibge, lat, lon` (mesma tabela do robô de RPA).
- `malhas_municipios.geojson`: FeatureCollection; cada feature com `properties.cod_ibge` (int) e `properties.municipio`.
- `clima_diario.csv`: `cod_ibge, data (AAAA-MM-DD), chuva_mm, et0_mm` — janeiro a junho dos anos de
  `safra.anos_disponiveis` (Open-Meteo Archive, `precipitation_sum`, `et0_fao_evapotranspiration`).
- `climatologia.csv`: `cod_ibge, dia_ano (1–366), chuva_media_mm, et0_media_mm` — média 1991–2020.
- `pedidos_safra.csv` (safra simulada, sintética) — **mesmas colunas da aba `solicitacoes` do robô**
  (`RPA/CONTRACTS.md`): `request_id, data_envio, municipio, uf, cod_ibge, service_id, confianca, decisao,
  motivo, docs_presentes, docs_faltantes, docs_ilegiveis, fonte_resposta` (listas separadas por `;`).
  Volume ~1.000 pedidos de jan–jun; mais pedidos de Garantia-Safra/CAF onde a perda estimada é maior; uma
  parte relevante travada por falta de `caf`.

## Saídas dos pipelines (DataFrames)
- `pipelines.clima.serie_safra(cod_ibge, ano)` → diária: `data, chuva, chuva_acum, normal_acum, et0, et0_acum`.
- `pipelines.risco.indicadores(ano, cultura, ate_data=None)` → um por município: `cod_ibge, municipio, uf,
  chuva_mm, normal_mm, anomalia_pct, maior_seca_dias, deficit_hidrico_mm, perda_estimada_pct, classe`
  (`classe` ∈ seguro|atencao|alerta|critico pelos limites de `risco.classes`). `ate_data` permite o "replay".
- `pipelines.demanda.resumo(pedidos)` → por município: `pedidos, familias_garantia_safra, travados_sem_caf,
  docs_mais_faltantes, revisao_humana`; e `por_servico(pedidos)`.
- `pipelines.recomendacoes.gerar(indicadores, demanda, cfg)` → lista de `Recomendacao(id, tipo
  (vistoria|mutirao_caf|convocacao), cod_ibge, municipio, prioridade (0–1), titulo, justificativa,
  evidencias: dict, acao_sugerida)`, ordenada por prioridade. `id` determinístico (tipo+município+ano).
- `pipelines.decisoes`: `registrar(decisao) / listar() / ja_decidida(id)` em `output/decisoes.jsonl`
  (`id, tipo, municipio, decisao (aprovada|editada|rejeitada), justificativa, mensagem, quando, usuario`);
  `rascunho_convocacao(recomendacao, rag=None)` → texto (RAG do genAI se disponível, senão template).
