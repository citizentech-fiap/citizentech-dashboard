# Contratos de dados do Mandacaru

## Entradas (snapshots em `data/`, gerados por `scripts/preparar_dados.py`)
- `municipios_semiarido.csv`: `municipio, uf, cod_ibge, lat, lon` (mesma tabela do robô de RPA).
- `malhas_municipios.geojson`: FeatureCollection; cada feature com `properties.cod_ibge` (int) e `properties.municipio`.
- `clima_diario.csv`: `cod_ibge, data (AAAA-MM-DD), chuva_mm, et0_mm` — janeiro a junho dos anos de
  `safra.anos_disponiveis` (Open-Meteo Archive, `precipitation_sum`, `et0_fao_evapotranspiration`).
- `climatologia.csv`: `cod_ibge, dia_ano (1–366), chuva_media_mm, et0_media_mm` — média 1991–2020.
  `dia_ano` usa o calendário bissexto de 2000: 29/02=60 e 01/03=61 em todos os anos.
  29/02 é a média dos oito anos bissextos; os outros dias usam os 30 anos. Em anos comuns,
  a comparação não usa o dia 60 (não desloca março nem interpola chuva).
- `pedidos_safra.csv` (safra simulada, sintética) — **mesmas colunas da aba `solicitacoes` do robô**
  (`RPA/CONTRACTS.md`), acrescidas de `ano`: `request_id, ano, data_envio, municipio, uf, cod_ibge, service_id, confianca, decisao,
  motivo, docs_presentes, docs_faltantes, docs_ilegiveis, fonte_resposta` (listas separadas por `;`).
  Volume de 1.000 pedidos de jan–jun **por ano**, no ano padrão e no ano de seca: 2.000 ao todo.
  Inteiramente **sintético**, seed fixa em `config.yaml: simulacao`; `request_id=SINT-<ano>-<n>` e
  `fonte_resposta=sintetica`. Sem nomes ou dados pessoais. Uma solicitação representa uma família
  fictícia; não é contagem oficial de inscritos. Maior perda aumenta o peso de volume municipal e
  dos serviços Garantia-Safra/CAF/Pronaf. Cerca de 33% dos pedidos GS/Pronaf ficam sem `caf`.
  Documentos canônicos vêm de `../RPA/config.yaml: services[].documentos_exigidos`.
  `resolvido` significa triagem respondida (pode haver documentos faltantes), não benefício concedido.
  O provider RPA deriva `ano` de `data_envio` quando a planilha não tem essa coluna e seleciona
  somente os campos deste contrato, sem expor dados pessoais adicionais da planilha.

## Saídas dos pipelines (DataFrames)
- `pipelines.clima.serie_safra(cod_ibge, ano)` → diária: `data, chuva, chuva_acum, normal_acum,
  et0, et0_acum, et0_normal, et0_normal_acum`. As duas últimas colunas trazem ET0 da normal
  1991–2020 alinhada por mês/dia, para comparar a satisfação hídrica no mesmo período.
- `pipelines.risco.indicadores(ano, cultura, ate_data=None)` → um por município: `cod_ibge, municipio, uf,
  chuva_mm, normal_mm, anomalia_pct, maior_seca_dias, deficit_hidrico_mm,
  isna_ano, isna_normal, razao_isna, perda_estimada_pct, classe`
  (`classe` ∈ seguro|atencao|alerta|critico pelos limites inferiores inclusivos de `risco.classes`).
  `ate_data` permite o replay (deve pertencer à safra do ano). `evolucao(ano, cultura,
  passo="semana")` retorna essas colunas mais `data`; passos `dia`, `semana` e `mes`,
  incluindo sempre o último dia da safra. Dados incompletos levantam erro claro, nunca viram chuva zero.
  `anomalia_pct=(chuva/normal-1)*100` (NaN se normal zero); `deficit_hidrico_mm` é ETc−ETa.
  Para ano e normal separadamente, ETc=Kc×ET0 e ETa=min(ETc,fator×chuva).
  ISNA (Índice de Satisfação das Necessidades de Água) = ETa/ETc, entre 0 e 1;
  `razao_isna=isna_ano/isna_normal` pode superar 1 (não é truncada).
  Perda (%) = clip(100×Ky×(1−razao_isna),0,100): adaptação acadêmica da resposta FAO-33
  **relativa à normal 1991–2020**, usando chuva e ET0 **do mesmo período**, inclusive no replay.
  Ano igual à normal ou satisfação maior que a normal → perda zero; chuva maior pode não
  bastar se ET0 também aumentar. Sem demanda, ISNA=1; normal com ISNA=0 levanta erro claro,
  pois não há referência para a razão. Déficit em mm continua absoluto, apenas diagnóstico.
  Sem balanço de solo ou fenologia; não é o indicador oficial INMET nem comprovação de perda
  ou direito ao pagamento do Garantia-Safra. As decisões de vistoria e pagamento são externas.
- `pipelines.demanda.resumo(pedidos)` → por município: `pedidos, familias_garantia_safra, travados_sem_caf,
  docs_mais_faltantes, revisao_humana, docs_completos`, além de `cod_ibge, municipio, uf`.
  `docs_mais_faltantes` é dict documento→contagem em ordem decrescente; `docs_completos` exige
  listas de faltantes/ilegíveis vazias e `decisao=resolvido`. `travados_sem_caf` considera apenas GS/Pronaf,
  com o token exato `caf` em faltantes. `familias_garantia_safra` aproxima inscritos pela contagem de
  solicitações GS (não verifica inscrição oficial). Filtre `pedidos.ano` **antes** de chamar `resumo`.
  `por_servico(pedidos)` → `cod_ibge, municipio, uf, service_id, pedidos`.
- `pipelines.recomendacoes.gerar(indicadores, demanda, cfg, ano)` → lista de `Recomendacao(id, tipo
  (vistoria|mutirao_caf|convocacao), cod_ibge, municipio, prioridade (0–1), titulo, justificativa,
  evidencias: dict, acao_sugerida)`, ordenada por prioridade. `id` determinístico (tipo+município+ano).
  `id=tipo-cod_ibge-ano`. Score = soma ponderada de perda/100, famílias/máximo e travados/máximo,
  dividida pela soma de `pesos_prioridade`; máximos zero contribuem zero. Mesmo score nas três
  regras municipais; desempate por código e tipo. Scores relativos à demanda do conjunto,
  não comparáveis entre anos.
- `pipelines.decisoes`: `registrar(decisao) / listar() / ja_decidida(id)` em `output/decisoes.jsonl`
  (`id, tipo, municipio, decisao (aprovada|editada|rejeitada), justificativa, mensagem, quando, usuario`);
  `rascunho_convocacao(recomendacao, rag=None)` → texto (RAG do genAI se disponível, senão template).
  `quando` omitido recebe ISO-8601 em UTC; histórico acrescentado, sem sobrescrita. Parâmetro
  opcional `caminho` permite testes isolados; arquivo ausente retorna lista vazia. Escrita local,
  um processo escritor; não substitui banco transacional para vários gestores simultâneos.
  O RAG só é usado se responder sem abstenção/bloqueio; erros mantêm o template local.
  Local e horário aguardam confirmação do gestor; nada é enviado.

## Operação e limites

`python scripts/preparar_dados.py` retoma municípios/intervalos ausentes ou incompletos;
`--forcar` renova snapshots e cache HTTP. As gravações de snapshots são atômicas.
Falhas de rede preservam progresso e dão saída 1; não se fabricam dados climáticos.
Uma chamada por município/safra e uma por município/normal 1991–2020. O Open-Meteo fornece
reanálise meteorológica, não uma estação de medição municipal; seu modelo padrão pode variar
entre períodos. Fontes: [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api)
(CC BY 4.0) e [IBGE Malhas](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3).
O cache histórico não expira automaticamente. Para novos dados, use `--forcar`.
Os providers levantam erros claros para a futura UI converter em avisos e oferecer snapshots;
a camada de dados não importa Streamlit nem mistura dados incompletos com indicadores válidos.
