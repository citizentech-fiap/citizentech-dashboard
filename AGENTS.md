# Regras do projeto para agentes de código

Repositório `citizentech-dashboard` — **Mandacaru**, painel de decisão (Streamlit) para o coordenador do
Garantia-Safra / técnico da EMATER no semiárido: mostra onde a seca está comprometendo a safra, quais
pedidos de agricultores estão travados e recomenda ações que o gestor aprova (vistoria, mutirão,
convocação). FIAP Global Solution, disciplina Front-end e Mobile Development em Sistemas de IA. Integra-se
a `citizentech-rpa` (`../RPA`, pedidos triados pelo robô) e `citizentech-genai` (`../genAI`, assistente RAG).

## Arquitetura obrigatória (a disciplina zera a nota de código monolítico)
| Pasta | Responsabilidade | Pode importar Streamlit? |
|---|---|---|
| `providers/` | acesso a dados externos: HTTP (Open-Meteo, IBGE), leitura da planilha do robô, RAG; parsing bruto, retry, cache em disco | **não** |
| `pipelines/` | transformação: limpeza, agregação, indicadores (modelo hídrico, risco), demanda, recomendações, decisões | **não** |
| `state/` | estado centralizado: única porta de entrada para `st.session_state` (chaves, defaults, getters/setters) | sim |
| `ui/` | design system (tema, cores semânticas, CSS), componentes reutilizáveis (cards, badges, gráficos, mapa), sidebar | sim |
| `features/` | telas (uma por aba), compõem `ui` + dados já processados | sim |
| `app.py` | ponto de entrada: configuração da página, sidebar, abas | sim |

- `providers/` e `pipelines/` são Python puro e testáveis sem a interface (`python -m pipelines.x` mostra
  resultados no console). Cache do Streamlit (`st.cache_data`/`st.cache_resource`) fica nas camadas de cima,
  envolvendo chamadas a providers/pipelines — nunca dentro deles.
- Configuração em `config.yaml` (carregada por `providers/config.py`); nada de números mágicos espalhados.

## Convenções
- Português do Brasil em código, comentários, interface e docs.
- Python: `..\.venv\Scripts\python.exe` (Windows). Não instale pacotes novos sem necessidade; se instalar,
  adicione em `requirements.txt`. Disponíveis: streamlit, plotly, matplotlib, pandas, numpy, requests, pyyaml.
- Dados: clima e mapas reais (Open-Meteo, IBGE); pedidos de agricultores **sintéticos** (marcar como tal).
  Nenhum dado pessoal real. Nunca leia nem exiba arquivos `.env`.
- Falhas previsíveis (API fora do ar, arquivo ausente) não derrubam o app: snapshot local + aviso na tela.

## Antes de terminar
- `..\.venv\Scripts\python -m unittest discover -s tests -q` (todos passam).
- Mexa só nos arquivos que a tarefa pede. Não faça commit nem push.
- Relatório curto ao final: arquivos, comandos rodados e resultados, decisões, pendências.
