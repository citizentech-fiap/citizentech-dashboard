# Relatório da Tarefa A — calibração por ISNA relativo

Correção aplicada no dashboard real em `C:/Users/akalu/Downloads/FIAP/GS/dashboard`. Como a sessão atual não conseguiu ler a pasta de preparação, as mesmas alterações foram reconstruídas a partir do código preservado na conversa e validadas novamente no repositório real.

## Arquivos aplicados

- `pipelines/modelo_hidrico.py`: ISNA do ano, ISNA da normal e `razao_isna`; perda relativa limitada a 0–100%. Chuva e ET0 históricas obrigatórias, sem fallback para o cálculo absoluto.
- `pipelines/clima.py`: `et0_normal` e `et0_normal_acum`, alinhadas por mês/dia ao calendário bissexto de 2000.
- `pipelines/risco.py`: propaga `isna_ano`, `isna_normal`, `razao_isna`; replay corta chuva e ET0 da normal na mesma data do ano.
- `config.yaml`: somente comentários do modelo; parâmetros numéricos preservados.
- `CONTRACTS.md`: novos campos, fórmula, referência histórica e extremos documentados.
- `tests/test_pipelines.py`: igualdade com a normal, metade da satisfação, chuva acima da normal, monotonicidade, extremos, referência inválida e ausência de vazamento temporal no replay.
- `data/pedidos_safra.csv`: 2.000 pedidos sintéticos regenerados (1.000 em 2012 e 1.000 em 2026), seed 42; documentos canônicos do RPA, sem nomes ou dados pessoais.
- `RELATORIO_TAREFA_A.md`: resultados recalibrados, validação no dashboard real e situação da limpeza.
- Sem alterações na interface, nos providers, nos snapshots de clima/mapas ou nas dependências. Nenhum commit ou push.

## Fórmula e limites

Para ano e normal separadamente: ETc=Kc×ΣET0; ETa=min(ETc,0,8×Σchuva); ISNA=ETa/ETc.
`perda_pct = clip(100 × Ky × (1 − ISNA_ano/ISNA_normal), 0, 100)`.
A razão não é truncada: satisfação acima da normal gera perda zero. As entradas históricas são somas das médias diárias de chuva e ET0 de 1991–2020 do mesmo período. Sem demanda, ISNA=1; se o ISNA da normal for zero, o modelo levanta erro claro. Déficit hídrico em mm permanece absoluto, apenas diagnóstico.
Chuva acima da normal com ET0 igual não gera perda. Se ET0 crescer suficientemente, o ISNA pode diminuir mesmo com chuva maior. Não se usa a anomalia de chuva isolada como perda.
Adaptação acadêmica da resposta FAO-33 ao ISNA relativo, sem validação como modelo oficial INMET. Não simula solo, irrigação ou fenologia e não comprova perda nem direito ao benefício. Vistoria e pagamento permanecem decisões externas.

## Testes e verificação no dashboard real

- `..\.venv\Scripts\python.exe -m unittest discover -s tests -q`: **35 testes passaram**, sem rede nem Streamlit, no dashboard real.
- Indicadores gerados para os seis anos abaixo; replay semanal de 2012/2026 conferido contra os indicadores finais, inclusive ISNAs e razão.
- Pedidos regenerados duas vezes com a mesma seed: resultados idênticos; 2.000 IDs únicos.
- Documentos dos pedidos conferidos contra o catálogo RPA; snapshots meteorológicos e de municípios/mapas preservados por SHA-256.
- Módulo `pipelines.recomendacoes` executado para 2012 e 2026 com demanda do mesmo ano, com saídas reproduzidas abaixo.

## Limpeza da .venv — pendente

A única pasta criada por esta tarefa dentro da `.venv` foi `C:/Users/akalu/Downloads/FIAP/GS/.venv/mandacaru-isna-x264_6cp`. Os testes e pacotes auxiliares criados nela permanecem contidos nessa pasta.
A sessão atual (`CodexSandboxOffline`) recebeu acesso negado ao ler os arquivos criados na sessão anterior (`CodexSandboxOnline`). A tentativa de remover exclusivamente essa pasta, com caminho absoluto previamente validado e `Remove-Item -LiteralPath ... -Recurse -Force`, foi rejeitada pela política automática de execução: `blocked by policy`, sem justificativa adicional.
**A pasta não foi removida.** Não foram alteradas permissões nem tentados meios alternativos de exclusão. Nenhum arquivo preexistente da `.venv` foi alterado ou apagado. A limpeza desse diretório é a única pendência.

## Classes por ano — milho, janeiro a junho

| Ano | Seguro | Atenção | Alerta | Crítico | Perda média (%) | Anomalia média de chuva (%) |
|---|---:|---:|---:|---:|---:|---:|
| 2012 | 0 | 0 | 0 | 23 | 92.05 | -70.59 |
| 2019 | 21 | 1 | 1 | 0 | 4.63 | +37.78 |
| 2020 | 23 | 0 | 0 | 0 | 0.00 | +108.47 |
| 2024 | 19 | 4 | 0 | 0 | 4.86 | +36.71 |
| 2025 | 14 | 6 | 2 | 1 | 14.06 | +17.72 |
| 2026 | 21 | 2 | 0 | 0 | 4.61 | +33.26 |

Médias aritméticas dos 23 municípios; não ponderadas por área agrícola ou população.

## Perda estimada por município (%) — milho

| Município | 2012 | 2019 | 2020 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| Petrolina | 100.00 | 9.40 | 0.00 | 0.00 | 29.51 | 0.00 |
| Serra Talhada | 100.00 | 0.00 | 0.00 | 0.00 | 24.39 | 8.89 |
| Arcoverde | 99.81 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Ouricuri | 99.29 | 7.90 | 0.00 | 0.81 | 27.34 | 0.00 |
| Salgueiro | 100.00 | 0.00 | 0.00 | 0.00 | 26.27 | 24.32 |
| Quixadá | 69.73 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Crateús | 84.61 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Tauá | 78.26 | 5.18 | 0.00 | 0.00 | 21.13 | 25.83 |
| Iguatu | 73.69 | 0.00 | 0.00 | 23.73 | 0.00 | 0.54 |
| Patos | 100.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Sousa | 100.00 | 0.00 | 0.00 | 0.00 | 0.00 | 8.36 |
| Cajazeiras | 92.34 | 0.00 | 0.00 | 26.41 | 10.85 | 17.60 |
| Caicó | 100.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Pau dos Ferros | 99.43 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Picos | 72.70 | 3.33 | 0.00 | 30.31 | 62.29 | 19.11 |
| São Raimundo Nonato | 88.35 | 40.24 | 0.00 | 30.57 | 48.85 | 1.30 |
| Juazeiro | 100.00 | 9.27 | 0.00 | 0.00 | 29.39 | 0.00 |
| Irecê | 97.71 | 31.15 | 0.00 | 0.00 | 43.41 | 0.00 |
| Senhor do Bonfim | 99.16 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Euclides da Cunha | 100.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Santana do Ipanema | 94.01 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Delmiro Gouveia | 100.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Nossa Senhora da Glória | 68.16 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Simulação e recomendações

| Ano | Pedidos | GS/Pronaf sem CAF | Recomendações |
|---|---:|---:|---:|
| 2012 | 1000 | 31.0% | 50 |
| 2026 | 1000 | 31.3% | 4 |

### Top 5 — 2012

```text
Safra 2012: 50 recomendações; top 5:
0.974 | convocacao | Salgueiro | Convocar 24 agricultores com documentação completa
  Perda estimada de 100% (critério 40%); chuva 76% abaixo da normal; 21 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 15 travados sem CAF; 24 com documentação completa.
0.974 | mutirao_caf | Salgueiro | Mutirão de inscrição no CAF em Salgueiro
  Perda estimada de 100% (critério 40%); chuva 76% abaixo da normal; 21 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 15 travados sem CAF; 24 com documentação completa.
0.974 | vistoria | Salgueiro | Indicar técnico vistoriador para a vistoria de perdas em Salgueiro
  Perda estimada de 100% (critério 40%); chuva 76% abaixo da normal; 21 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 15 travados sem CAF; 24 com documentação completa.
0.920 | convocacao | Petrolina | Convocar 34 agricultores com documentação completa
  Perda estimada de 100% (critério 40%); chuva 81% abaixo da normal; 23 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 9 travados sem CAF; 34 com documentação completa.
0.920 | vistoria | Petrolina | Indicar técnico vistoriador para a vistoria de perdas em Petrolina
  Perda estimada de 100% (critério 40%); chuva 81% abaixo da normal; 23 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 9 travados sem CAF; 34 com documentação completa.
```

### Top 5 — 2026 (somente quatro recomendações elegíveis)

```text
Safra 2026: 4 recomendações; top 5:
0.622 | mutirao_caf | Salgueiro | Mutirão de inscrição no CAF em Salgueiro
  Perda estimada de 24% (critério 40%); chuva 16% abaixo da normal; 27 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 12 travados sem CAF; 31 com documentação completa.
0.546 | mutirao_caf | Tauá | Mutirão de inscrição no CAF em Tauá
  Perda estimada de 26% (critério 40%); chuva 12% abaixo da normal; 21 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 11 travados sem CAF; 39 com documentação completa.
0.449 | mutirao_caf | Cajazeiras | Mutirão de inscrição no CAF em Cajazeiras
  Perda estimada de 18% (critério 40%); chuva 14% abaixo da normal; 16 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 11 travados sem CAF; 40 com documentação completa.
0.367 | mutirao_caf | Ouricuri | Mutirão de inscrição no CAF em Ouricuri
  Perda estimada de 0% (critério 40%); chuva 14% acima da normal; 18 famílias inscritas na simulação do Garantia-Safra. Estimativa acadêmica: pagamento depende dos dois indicadores, incluindo vistoria. 10 travados sem CAF; 27 com documentação completa.
```
