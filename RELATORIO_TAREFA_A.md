# Relatório da Tarefa A — Mandacaru

Camada de dados concluída sem Streamlit. Download real dos 23 municípios e de todos os oito anos configurados; nenhuma chuva ou malha inventada.

## Arquivos

- `providers/`: config, HTTP resiliente/cache/gzip, Open-Meteo, IBGE, RPA, RAG opcional e snapshots.
- `pipelines/`: clima, modelo hídrico, risco/replay, demanda, recomendações e decisões/rascunhos.
- `scripts/preparar_dados.py`, `scripts/__init__.py` e três módulos de testes.
- Quatro snapshots em `data/`, `CONTRACTS.md`, `config.yaml` e este relatório.
- Nenhuma alteração em state/ui/features/app; nenhum commit ou push.

## Snapshots reais e simulação

| Arquivo | Registros | Bytes |
|---|---:|---:|
| malhas_municipios.geojson | 23 | 18.596 |
| clima_diario.csv | 33.396 | 967.594 |
| climatologia.csv | 8.418 | 368.509 |
| pedidos_safra.csv | 2.000 | 369.500 |

Clima: jan–jun de 2012, 2013, 2016, 2019, 2020, 2024, 2025 e 2026. Normal: 1991–2020, 366 dias de calendário por município.
Fontes: [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) (reanálise; CC BY 4.0) e [IBGE Malhas](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3).
Houve respostas HTTP 429 na climatologia; a retomada com espaçamento concluiu o download. Log: `output/preparacao.log`.

Pedidos inteiramente sintéticos: 1.000 por ano, seed 42, sem nomes ou identificadores pessoais; documentos conferidos contra o catálogo real do RPA.

- 2012: 190/610 pedidos GS/Pronaf sem CAF (31,1%).
- 2026: 181/564 pedidos GS/Pronaf sem CAF (32,1%).

## Validação

- `..\.venv\Scripts\python.exe scripts/preparar_dados.py`: concluído, snapshots completos e pedidos gerados.
- `..\.venv\Scripts\python.exe -m unittest discover -s tests -q`: 30 testes passaram, sem rede ou Streamlit.
- Segunda execução de `preparar()` com HTTP bloqueado: retorno 0, zero chamadas de rede.
- Conferidos municípios/anos, dias, colunas, duplicidades, documentos e proporções de CAF.
- Replay semanal: 621 linhas por ano; última data coincide com os indicadores finais.
- Importações e AST verificadas sem Streamlit; `git diff --check` passou.
- Também executados os módulos clima, demanda, modelo_hidrico e decisoes; sem erro.

## Decisões e limitações

- FAO-33 agregado: ETc=Kc×ET0; ETa=min(ETc,0,8×chuva); perda=clip(100×Ky×(1−ETa/ETc),0,100). Sem demanda, perda zero. Não simula solo, irrigação, fenologia ou distribuição intrassazonal.
- Estimativa acadêmica, sem validar o modelo oficial do INMET. O pagamento depende de dois indicadores com perda mínima de 40%; pedir vistoria permanece decisão humana.
- Calendário de 2000: 29/02 usa oito anos bissextos; março não desloca em anos comuns.
- `config.yaml` recebeu parâmetros de retry/espaçamento e simulação para evitar números mágicos; fonte descrita como reanálise. Parâmetros de safra, modelo e risco preservados.
- Contrato ampliado com `ano` e `docs_completos`; demanda filtrada por ano antes das recomendações.
- Famílias inscritas aproximadas pelas solicitações sintéticas GS; não representam cadastro oficial nem contagem de pessoas reais.
- Prioridade normaliza perda, famílias e gargalo; empates por código/tipo. Scores entre anos usam máximos de demanda próprios.
- RAG testado com dublês; indisponibilidade/abstenção usa template. Integração real com LLM não executada. Nenhum .env lido ou mensagem enviada.
- JSONL pressupõe um processo escritor. A UI futura deve transformar erros claros em avisos e oferecer snapshots.
- Cache histórico renovado com `--forcar`. RPA/genAI e dependências existentes não modificados. Sem pendências na camada solicitada.

## Saídas solicitadas dos módulos

### `python -m pipelines.risco --ano 2012`

```text
Safra 2012 — milho — estimativa acadêmica FAO-33
 cod_ibge               municipio uf  chuva_mm  normal_mm  anomalia_pct  maior_seca_dias  deficit_hidrico_mm  perda_estimada_pct  classe
  2611101               Petrolina PE     56.90     297.84        -80.90              103             1013.61              100.00 critico
  2613909           Serra Talhada PE     70.30     396.03        -82.25               47              910.28              100.00 critico
  2601201               Arcoverde PE     55.80     247.06        -77.41               37              790.29              100.00 critico
  2609907                Ouricuri PE    117.30     449.43        -73.90               38              816.60              100.00 critico
  2612208               Salgueiro PE     98.70     410.25        -75.94               47              894.94              100.00 critico
  2311306                 Quixadá CE    317.30     616.89        -48.56               25              567.66               86.38 critico
  2304103                 Crateús CE    200.00     526.36        -62.00               31              670.94              100.00 critico
  2313302                    Tauá CE    276.70     642.16        -56.91               29              553.95               89.31 critico
  2305506                  Iguatu CE    327.10     688.32        -52.48               24              561.49               85.26 critico
  2510808                   Patos PB     63.80     388.80        -83.59              102              953.74              100.00 critico
  2516201                   Sousa PB    114.20     520.83        -78.07               31              869.64              100.00 critico
  2503704              Cajazeiras PB    187.00     586.69        -68.13               29              786.89              100.00 critico
  2402006                   Caicó RN     82.20     366.69        -77.58               73              964.77              100.00 critico
  2409407          Pau dos Ferros RN    125.50     516.96        -75.72               30              819.78              100.00 critico
  2208007                   Picos PI    290.70     571.90        -49.17               62              633.51               91.43 critico
  2210607     São Raimundo Nonato PI    165.60     466.55        -64.51              102              737.54              100.00 critico
  2918407                Juazeiro BA     56.90     297.84        -80.90              103             1015.25              100.00 critico
  2914604                   Irecê BA     76.40     296.62        -74.24               86              852.50              100.00 critico
  2930105        Senhor do Bonfim BA    114.50     457.13        -74.95               55              675.79              100.00 critico
  2910701       Euclides da Cunha BA     52.60     269.75        -80.50               57              750.74              100.00 critico
  2708006      Santana do Ipanema AL     76.10     282.09        -73.02               30              742.90              100.00 critico
  2702405         Delmiro Gouveia AL     46.50     242.30        -80.81               91              860.83              100.00 critico
  2804508 Nossa Senhora da Glória SE    149.40     311.81        -52.09               20              606.31              100.00 critico
Classes: {'critico': 23}
```

### `python -m pipelines.recomendacoes --ano 2012`

```text
Safra 2012: 53 recomendações; top 5:
1.000 | convocacao | Euclides da Cunha | Convocar 25 agricultores com documentação completa
  Perda estimada de 100% (critério 40%); chuva 81% abaixo da normal; 25 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 16 travados sem CAF; 25 com documentação completa.
1.000 | mutirao_caf | Euclides da Cunha | Mutirão de inscrição no CAF em Euclides da Cunha
  Perda estimada de 100% (critério 40%); chuva 81% abaixo da normal; 25 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 16 travados sem CAF; 25 com documentação completa.
1.000 | vistoria | Euclides da Cunha | Indicar técnico vistoriador para a vistoria de perdas em Euclides da Cunha
  Perda estimada de 100% (critério 40%); chuva 81% abaixo da normal; 25 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 16 travados sem CAF; 25 com documentação completa.
0.889 | convocacao | Santana do Ipanema | Convocar 27 agricultores com documentação completa
  Perda estimada de 100% (critério 40%); chuva 73% abaixo da normal; 22 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 10 travados sem CAF; 27 com documentação completa.
0.889 | mutirao_caf | Santana do Ipanema | Mutirão de inscrição no CAF em Santana do Ipanema
  Perda estimada de 100% (critério 40%); chuva 73% abaixo da normal; 22 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 10 travados sem CAF; 27 com documentação completa.
```

### `python -m pipelines.risco --ano 2026`

```text
Safra 2026 — milho — estimativa acadêmica FAO-33
 cod_ibge               municipio uf  chuva_mm  normal_mm  anomalia_pct  maior_seca_dias  deficit_hidrico_mm  perda_estimada_pct  classe
  2611101               Petrolina PE    550.40     292.09         88.44               23              393.21               58.97  alerta
  2613909           Serra Talhada PE    367.70     393.02         -6.44               16              490.86               78.16 critico
  2601201               Arcoverde PE    447.80     244.04         83.49               12              330.63               60.00  alerta
  2609907                Ouricuri PE    509.20     445.25         14.36               31              356.37               58.33  alerta
  2612208               Salgueiro PE    342.70     408.23        -16.05               26              534.19               82.60 critico
  2311306                 Quixadá CE    763.80     613.63         24.47                8              100.87               17.71  seguro
  2304103                 Crateús CE    760.70     521.53         45.86               15              110.51               19.21  seguro
  2313302                    Tauá CE    560.80     639.38        -12.29               15              291.11               49.19  alerta
  2305506                  Iguatu CE    713.90     684.06          4.36               19              169.85               28.65 atencao
  2510808                   Patos PB    581.20     385.54         50.75               15              356.21               54.22  alerta
  2516201                   Sousa PB    484.20     516.76         -6.30               22              402.45               63.69 critico
  2503704              Cajazeiras PB    501.60     580.12        -13.54               39              366.74               59.69  alerta
  2402006                   Caicó RN    687.30     363.34         89.16               19              269.69               41.13  alerta
  2409407          Pau dos Ferros RN    645.20     512.64         25.86               16              268.91               42.82  alerta
  2208007                   Picos PI    514.30     563.57         -8.74               39              352.56               57.68  alerta
  2210607     São Raimundo Nonato PI    500.00     460.97          8.47               52              383.67               61.20 critico
  2918407                Juazeiro BA    550.40     292.09         88.44               23              393.25               58.97  alerta
  2914604                   Irecê BA    334.30     290.58         15.04               31              488.93               80.80 critico
  2930105        Senhor do Bonfim BA    606.20     436.74         38.80               14              194.56               35.79 atencao
  2910701       Euclides da Cunha BA    401.20     263.65         52.17               19              402.06               69.51 critico
  2708006      Santana do Ipanema AL    473.70     276.89         71.08               17              342.43               59.34  alerta
  2702405         Delmiro Gouveia AL    405.30     239.02         69.57               19              467.10               73.78 critico
  2804508 Nossa Senhora da Glória SE    482.30     305.32         57.96               10              336.04               58.19  alerta
Classes: {'alerta': 12, 'critico': 7, 'seguro': 2, 'atencao': 2}
```

### `python -m pipelines.recomendacoes --ano 2026`

```text
Safra 2026: 45 recomendações; top 5:
0.859 | convocacao | Salgueiro | Convocar 34 agricultores com documentação completa
  Perda estimada de 83% (critério 40%); chuva 16% abaixo da normal; 27 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 11 travados sem CAF; 34 com documentação completa.
0.859 | mutirao_caf | Salgueiro | Mutirão de inscrição no CAF em Salgueiro
  Perda estimada de 83% (critério 40%); chuva 16% abaixo da normal; 27 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 11 travados sem CAF; 34 com documentação completa.
0.859 | vistoria | Salgueiro | Indicar técnico vistoriador para a vistoria de perdas em Salgueiro
  Perda estimada de 83% (critério 40%); chuva 16% abaixo da normal; 27 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 11 travados sem CAF; 34 com documentação completa.
0.790 | convocacao | Irecê | Convocar 44 agricultores com documentação completa
  Perda estimada de 81% (critério 40%); chuva 15% acima da normal; 28 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 6 travados sem CAF; 44 com documentação completa.
0.790 | vistoria | Irecê | Indicar técnico vistoriador para a vistoria de perdas em Irecê
  Perda estimada de 81% (critério 40%); chuva 15% acima da normal; 28 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 6 travados sem CAF; 44 com documentação completa.
```
