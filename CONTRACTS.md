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
  Volume de 1.000 pedidos de jan–jun **por ano**, em todas as safras 2012–2026: 15.000 ao todo.
  Inteiramente **sintético**, seed fixa em `config.yaml: simulacao`; `request_id=SINT-<ano>-<n>` e
  `fonte_resposta=sintetica`. Sem nomes ou dados pessoais. Uma solicitação representa uma família
  fictícia; não é contagem oficial de inscritos. Maior perda aumenta o peso de volume municipal e
  dos serviços Garantia-Safra/CAF/Pronaf. Cerca de 33% dos pedidos GS/Pronaf ficam sem `caf`.
  Documentos canônicos vêm de `../RPA/config.yaml: services[].documentos_exigidos`.
  `resolvido` significa triagem respondida (pode haver documentos faltantes), não benefício concedido.
  O provider RPA deriva `ano` de `data_envio` quando a planilha não tem essa coluna e seleciona
  somente os campos deste contrato, sem expor dados pessoais adicionais da planilha.
- `pam_municipios.csv`: `cod_ibge, ano, cultura (milho|feijao), area_plantada_ha,
  area_colhida_ha, producao_t` — PAM/SIDRA tabela 1612, 23 municípios, 2002–2025.
  Variáveis 109/216/214 e produtos c81=2711/2702. Pela convenção do IBGE, `-` é **zero
  absoluto** (safra perdida) e vira 0; `..`, `...` e `X` (não se aplica, não disponível, sigilo)
  são **NaN**, nunca zero. Consulta anual com todos os municípios; chave única município/ano/cultura.
- `garantia_safra_pagamentos.csv`: `cod_ibge, municipio, uf, safra, familias,
  valor_total, meses_com_pagamento` — somente agregados municipais de parcelas positivas.
  `familias` conta NIS distintos **na safra inteira**, não soma contagens mensais;
  aproxima famílias por beneficiários, sem verificar composição familiar. Valores em reais;
  soma em centavos decimais, convertida para número apenas na saída. Meses é contagem
  distinta de meses com parcela positiva no município. Município/safra sem pagamento
  não ganha linha: sua interpretação depende da cobertura abaixo.
- `garantia_safra_cobertura.json`: mapa `AAAAMM -> disponivel|inexistente|nao_publicado`,
  sem informação individual. `inexistente` é HTTP 404/410; `nao_publicado` significa
  ausência no catálogo da página oficial. Falhas de rede, HTTP 403/405/CAPTCHA e
  formato inesperado **não** significam ausência de pagamento nem são marcadas como concluídas.
  O período solicitado é 2012-01–2026-10; catálogo consultado em 05/11/2026:
  2013-01–2026-09, com algumas lacunas (não se assume continuidade).

### Garantia-Safra: formato observado, atribuição e privacidade

ZIP 201305 inspecionado **só em memória**: CSV separado por `;`, entre aspas,
codificação latin-1, com colunas reais `MÊS REFERÊNCIA`, `UF`, `CÓDIGO MUNICÍPIO SIAFI`,
`NOME MUNICÍPIO`, `NIS FAVORECIDO`, `NOME FAVORECIDO`, `VALOR PARCELA`.
O [dicionário oficial](https://portaldatransparencia.gov.br/dicionario-de-dados/garantia-safra)
define a referência como ano/mês da folha de pagamento. Não há ano-safra no arquivo.
Adotamos a convenção analítica **julho de Y a junho de Y+1 → safra Y**: agrupa parcelas
após a estação jan–jun da safra modelada. Não é vinculação oficial; atrasos e pagamentos
de safras anteriores podem deslocar valores entre safras analíticas. Receber pagamento
não é, sozinho, comprovação da perda PAM municipal ou da acurácia do modelo climático.

Municípios são mapeados pelo par nome normalizado (sem acentos, caixa alta, espaços
compactados) + UF em `municipios_semiarido.csv`; código SIAFI não é código IBGE.
Em 201305 os **23/23** municípios casaram, sem alias ou caso sem match no recorte.
Demais municípios do Brasil são descartados por estarem fora do recorte; ausência de
um município num mês não prova falha de match nem ausência de perda agrícola.

**Privacidade obrigatória:** `providers.http.get(..., cache=False)` em todos os downloads
do Garantia-Safra. ZIP e CSV bruto nunca são gravados, extraídos nem cacheados. O parser
seleciona apenas referência, UF, município, NIS e valor (`NOME FAVORECIDO` não é carregado).
NIS do recorte permanece em conjuntos privados em memória para deduplicação durante
uma safra; só a cardinalidade sai da função. Sem nomes, NIS, hashes identificáveis ou
linhas individuais em snapshots, logs, fixtures ou metadados. Testes usam ZIP sintético.
Cada safra é salva atomicamente somente depois de todos os seus meses serem processados;
falha preserva o agregado anterior e exige reprocessar toda a safra para deduplicar,
sem persistir identificadores entre execuções.

## Saídas dos pipelines (DataFrames)
- `pipelines.clima.serie_safra(cod_ibge, ano)` → diária: `data, chuva, chuva_acum, normal_acum,
  et0, et0_acum, et0_normal, et0_normal_acum`. As duas últimas colunas trazem ET0 da normal
  1991–2020 alinhada por mês/dia, para comparar a satisfação hídrica no mesmo período.
- `pipelines.risco.indicadores(ano, cultura, ate_data=None)` → um por município: `cod_ibge, municipio, uf,
  chuva_mm, normal_mm, anomalia_pct, maior_seca_dias, deficit_hidrico_mm,
  isna_ano, isna_normal, razao_isna, perda_estimada_pct, estimavel, classe`.
  `estimavel` é booleano: corte a partir de `safra.inicio_estimativa` (01/03) ou safra completa.
  Antes disso, perda é **NaN**, nunca zero. `classe` vem da anomalia de chuva:
  ≥0 seguro, [-20,0) atenção, [-40,-20) alerta, abaixo de -40 crítico,
  limites em `risco.classes_chuva`. Quando estimável, classes pelos limites inferiores
  inclusivos de `risco.classes` (0/20/40/60). `evolucao` aplica a mesma regra a cada data.
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
  Vistoria exige `estimavel=True`; antes de março o termo risco no score é zero,
  preservando pesos/denominador. Mutirão e convocação mantêm suas regras (convocação
  pode usar classe por chuva). A justificativa informa que é cedo para estimar perda.
- `pipelines.realidade.perda_real(cultura, dados=None)` → colunas PAM mais
  `producao_media_10_anos_t, perda_producao_pct, perda_area_pct`.
  Média dos **dez anos calendários anteriores**, excluindo o próprio ano. Por cautela,
  exige dez produções disponíveis; um símbolo/ano faltante deixa a média e a perda
  de produção como NaN. Média zero também gera NaN. Perda produção =
  `clip(100*(1-producao/media),0,100)`; perda área =
  `clip(100*(1-colhida/plantada),0,100)` (NaN se área plantada zero/ausente).
  Mudanças de área, cultura e irrigação podem causar divergência com o modelo hídrico.
  `dados` opcional permite verificação com séries conhecidas, sem rede.
- `pipelines.realidade.pagamentos()` → snapshot municipal de pagamentos.
- `pipelines.realidade.validacao(cultura)` → dict com `dados` (join município/ano),
  `matriz` (linhas estimado ≥40 falso/verdadeiro; colunas real ≥40 falso/verdadeiro),
  `acuracia`, `spearman`, `pares_validos`, `pares_excluidos`, `divergencias` (10 maiores
  diferenças absolutas em pontos percentuais), `avisos`. Janela 2012–2025 (configurada).
  Verdade de comparação = **perda_producao_pct** PAM; perda de área é diagnóstico.
  Matriz, acurácia e Spearman excluem pares sem medida; Spearman usa Pearson dos postos
  médios (empates incluídos), NaN se série constante/insuficiente. Join de pagamentos
  inclui `cobertura_pagamentos_completa` e `pagou_garantia_safra` booleano anulável:
  verdadeiro se há pagamentos, falso só se todos os 12 meses estão disponíveis,
  desconhecido se não há registro e a cobertura está incompleta. Números de famílias/
  valores ausentes só viram zero quando a cobertura é completa.
  **Retrospectiva apenas:** nenhum dado PAM/pagamento entra nas recomendações da safra.
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
`--etapas clima pedidos` ou `--etapas pam garantia_safra` permitem retomar grupos de etapas.
PAM é retomada por ano (incluindo NaN legítimo); pagamentos, por safra inteira concluída.
Pausas entre downloads em `fontes.intervalo_download_s`; retries/backoff do cliente HTTP
para rede, 429 e 5xx. HTTP 405 recebe tentativas espaçadas por
`fontes.backoff_download_s` exponencial (60/120/240 s por padrão), pois o acesso observado
voltou após intervalo. CAPTCHA não é resolvido nem contornado; se o servidor continuar
bloqueando, a etapa avisa e sai com erro, preservando os agregados já concluídos.


## Resumo da semana

`pipelines.resumo.fatos(indicadores, demanda, recomendacoes, historico_decisoes, cfg, ano,
ate_data, realidade=None)` retorna JSON serializável: safra, data de corte, `estimavel`,
municípios por classe, cinco mais críticos (perda quando estimável, anomalia antes disso),
ações pendentes por tipo (exclui IDs decididos), decisões da safra e municípios selecionados
nos últimos sete dias em relação ao relógio atual UTC (aprovadas, ajustadas, recusadas),
travados sem CAF com `simulado` explícito e mediana de perda real, somente se publicada.
Os indicadores fornecidos determinam o recorte; a aba resumo usa safra completa, como a fila de ações.
Retrospectiva não entra no gerador de recomendações. Nenhum pedido individual vai ao LLM.

`numeros(texto)` normaliza números com decimal por vírgula ou ponto, milhares brasileiros,
percentuais e componentes de datas. `numeros_desconhecidos(texto, fatos)` compara os valores
normalizados com os presentes no JSON: é um guardrail de pertinência numérica, não uma
verificação semântica de relações entre números. Valores ausentes nos fatos geram aviso e
opção de template. O gestor revisa o texto editável antes de baixar. O template tem seis
frases e usa somente os agregados. Cache por SHA-256 do JSON ordenado na sessão evita nova
chamada para fatos iguais; `make_llm` mantém seu cache ligado e seu fallback configurado.
Falhas de pacote, chave, rede ou geração retornam motivo curto e template, sem traceback.


## Contratos da revisão Front-end

- `providers.config.carregar(arquivo=None)`: cache LRU por caminho absoluto e `st_mtime_ns`;
  devolve cópia profunda. Alterar o retorno não altera chamadas seguintes.
- `providers.atualizacao_clima.baixar_clima`: mesma rotina atômica para CLI e app, sem Streamlit.
  `state.dados.atualizar_municipio` não tem cache de resultado: guarda `(codigo, ano, solicitacao)`
  em `store`, inclusive tentativa concluída com falha; nova solicitação permite tentar de novo.
  Invalida indicadores, série, evolução, contexto e validação; mtime também compõe as chaves.
- `pipelines.decisoes.salvar_decisao(rec, escolha, justificativa, mensagem, usuario, cfg=None)`:
  exige gestor, situação válida, motivo na rejeição e mensagem para mutirão/convocação aprovados.
  Impede ID repetido. `.eml` atômico sem destinatário, `X-Unsent: 1`; falha ao registrar desfaz o arquivo.
  Log inteiro substituído atomicamente, preservando registros anteriores. Continua sendo um escritor local.
- `pipelines.decisoes.selos(historico)` retorna mapa ID → registro completo; `editada` aparece como
  “Aprovada com ajustes”. Mapa considera aprovadas/editadas da safra selecionada, sem mudar risco.
- `gestor` inicia vazio em `store`; UI desabilita decisões e pipeline também valida a identidade.
  Features fornecem callbacks de gravação/rascunho; UI recebe configuração, dados e callbacks.
- Dispersão/placar usam UF e safra selecionadas; limiar do Panorama é exploratório, classes oficiais intactas.
  Gráficos de contagem recebem DataFrames `categoria, quantidade`; vazio retorna `None`.
- `formatacao.numero/percentual` são funções puras compartilhadas. `resumo.fatos_exibicao` cria cópia
  com floats em pt-BR; fatos originais permanecem numéricos para hash, LLM e checagem de números.
- Aplicação independente usa snapshots e templates; genAI e RPA são integrações opcionais.
  Chave de Gemini no deploy: secret raiz `GEMINI_API_KEY`; pacote/índice genAI continuam opcionais.
