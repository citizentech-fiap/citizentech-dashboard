# Tarefa B — interface Mandacaru

Implementação concluída em 05/11/2026. Abertura na seca de 2012, com aviso de demonstração,
filtros compartilhados e jornada panorama → raio-x → mesa de decisão → assistente.

## Arquivos

Criados:
- `app.py`.
- `state/store.py`, `state/dados.py`.
- `ui/tema.py`, `ui/componentes.py`, `ui/graficos.py`, `ui/sidebar.py`.
- `features/panorama.py`, `features/municipio.py`, `features/decisoes.py`, `features/assistente.py`.
- `assets/logo.svg`, `.streamlit/config.toml`.
- `tests/test_interface.py` e este relatório.

Alterados: `config.yaml` (parâmetros de interface/cache/mapa) e `requirements.txt`
(versões mínimas das duas dependências existentes usadas: Streamlit 1.66.1 e Plotly 7.1.0).
Nenhum pacote instalado. Providers, pipelines, scripts, snapshots e README preservados.
Sem commit ou push.

## Onde demonstrar cada requisito

| Requisito | Arquivo:função / recurso |
|---|---|
| Entrada fina, abas, resumo calculado e aviso de 2012 | `app.py:principal` |
| Único acesso direto a `st.session_state` | `state/store.py:obter`, `definir`, `iniciar`; callbacks `abrir_municipio`, `selecionar_municipio` |
| Cache de dados por ano, cultura, UFs, serviço, limiar e corte | `state/dados.py:contexto`, `indicadores`, `serie`, `evolucao`; todos com `st.cache_data` |
| Expiração e invalidação quando snapshots mudam | `state/dados.py:versao_snapshots`; TTLs em `config.yaml:interface` |
| Cache do recurso RAG, inicialização sob demanda e uso serializado | `state/dados.py:recurso_rag` (`st.cache_resource`), `perguntar`, `rascunhar` |
| Cinco filtros globais, ano 2012 rotulado e padrão 40% | `ui/sidebar.py:renderizar`; defaults em `state/store.py:iniciar` |
| Mês de replay exclusivo do panorama | `features/panorama.py:renderizar`; indicadores até o último dia do mês |
| Mapa Plotly dos polígonos IBGE e hover completo | `ui/graficos.py:mapa_perdas`; perda, classe, chuva/normal e pedidos |
| Curva Plotly, normal e faixa de ETc | `ui/graficos.py:grafico_chuva`; usada no panorama (três miniaturas) e no raio-x |
| Critério oficial no eixo correto | `ui/graficos.py:grafico_chuva`; mm à esquerda, perda à direita, linha oficial de 40% e linha adicional de triagem quando diferente |
| Barras Plotly por serviço e documento faltante | `ui/graficos.py:barras_servicos`, `barras_documentos`; tela `features/municipio.py:renderizar` |
| Calendário Matplotlib de dias secos | `ui/graficos.py:calendario_seco`; tela `features/municipio.py:renderizar` |
| Componentização real | `ui/componentes.py:kpi` (três telas), `badge_risco` (três telas), `cartao_recomendacao`; `grafico_chuva` (duas telas) |
| Tema quente, cacto SVG e tokens próprios | `.streamlit/config.toml`, `assets/logo.svg`, `ui/tema.py:aplicar` |
| Mesma escala de risco e rótulos além de cores | `ui/tema.py:CORES`, `RISCOS`, `escala_risco`, `legenda`; limites do modelo em `config.yaml:risco.classes` |
| Latência visível e atualização por município | `ui/sidebar.py:atualizar` (`st.progress`, `st.status`); `state/dados.py:atualizar_municipio` reutiliza `scripts.preparar_dados.baixar_clima` e o provider Open-Meteo |
| Snapshot preservado em falha da API | `ui/sidebar.py:atualizar`; a preparação existente só substitui um intervalo após resposta válida |
| Ausência de arquivos sem derrubar o app | `state/dados.py:catalogos`, `pedidos`; `app.py:principal` trata indisponibilidade climática e orienta recuperação |
| Cartões com prioridade, números e navegação às evidências | `ui/componentes.py:cartao_recomendacao`, `abrir_raio_x`; `state/store.py:abrir_municipio` abre a aba e seleciona o município |
| Aprovar, editar data/local/plano ou rejeitar com justificativa | `features/decisoes.py:_formulario` (`st.form`); validação adicional em `state/dados.py:salvar_decisao` |
| Rascunho, template/RAG, placeholder e confirmação humana | `features/decisoes.py:_formulario`, `_revisar`; `state/dados.py:rascunhar` chama `pipelines.decisoes.rascunho_convocacao` |
| Mensagem revisada em `.eml` e auditoria JSONL | `state/dados.py:salvar_decisao`; usa gravação atômica existente e `pipelines.decisoes.registrar` |
| Recomendação decidida sai da fila e permanece no histórico | `features/decisoes.py:renderizar`; paginação de cinco cartões e tabela com CSV para download |
| Perda é aproximação, decisão é humana | `ui/componentes.py:aviso_modelo`; explicações no raio-x e nos cartões |
| Chat, fontes e aviso quando indisponível | `features/assistente.py:renderizar`, `_fontes`; `state/dados.py:perguntar` reutiliza `providers.genai` |
| Estado positivo na safra normal de 2026 | `features/decisoes.py:renderizar`; mensagem “Nenhum município atingiu o critério de 40% nesta safra” |

## Decisões de interface

- O limiar é exploratório: modifica o destaque no panorama, o diagnóstico no raio-x e filtra
  propostas climáticas. As regras mínimas existentes de vistoria/convocação continuam válidas ao
  baixar o limiar. As classes calibradas não mudam. Mutirão de CAF depende do gargalo documental.
- Com todos os municípios, milho e limiar de 40%, 2026 mantém quatro propostas administrativas
  de mutirão; não gera vistoria ou convocação por seca. Isso é explicado no estado positivo.
- O replay limita apenas o clima no panorama. Os pedidos exibidos ali cobrem a safra inteira,
  com esse escopo escrito na tela. Raio-x e decisões usam sempre a safra completa.
- Os snapshots de pedidos contêm 2012 e 2026. Nos demais anos, a tela avisa que demanda está
  sem dados; os zeros não são apresentados como comprovação de ausência de necessidade.
- RAG só inicializa ao conectar o assistente ou preparar uma convocação. Apenas a aba ativa
  é renderizada. O histórico de chat é separado por recorte; perguntas ao RAG filtram o serviço.
  A interface esclarece que a base documental não contém o clima nem os pedidos.
- A revisão de convocação/mutirão não grava decisão ou mensagem antes de confirmar.
  `.eml` é rascunho (`X-Unsent: 1`), sem destinatário, sem envio. Data/local/plano entram no texto
  e no registro. Se a gravação do log falha, a nova mensagem é removida para permitir nova tentativa.
- O identificador de recomendação do contrato é municipal/anual; uma decisão continua válida
  ao trocar cultura ou serviço. A justificativa registra o contexto do filtro usado na decisão.

## Validação executada

Comando obrigatório, após a última alteração de código:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

**Resultado: 44 testes em 20,463 s, todos aprovados** — 35 existentes e nove novos.
O runner do Streamlit emite avisos esperados de contexto/cache fora do servidor; não houve
exceções no app. Foi corrigido um aviso de valor inicial duplicado ao retomar a edição do plano.

Os nove testes novos incluem oito cenários com AppTest e uma validação de persistência:

1. Abertura em 2012, filtros combinados, replay, gráfico Matplotlib e navegação por evidências.
2. Convocação: logística obrigatória, edição, retorno à proposta preservando campos,
   confirmação obrigatória, `.eml` válido e retirada da fila.
3. Rejeição sem justificativa bloqueada, rejeição justificada e aprovação de vistoria.
4. Estado normal de 2026, quatro mutirões, ano sem pedidos e UFs vazias.
5. Open-Meteo offline: chamada ao provider, snapshot byte a byte preservado e aviso na tela.
6. Chat indisponível e chat com fontes simuladas, filtragem por serviço e isolamento de histórico.
7. Malhas/pedidos ausentes, clima incompleto e verificação de que o critério usa o eixo percentual.
8. Rerun e mudança de limiar reutilizam indicadores; mudança de cultura recalcula.
9. Falha de persistência recuperável e bloqueio de gravação duplicada.

As decisões dos testes foram gravadas em diretórios temporários, removidos automaticamente.
Nenhuma decisão de teste foi acrescentada ao histórico de uso do projeto.

Servidor headless:

```powershell
..\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8599 --server.address 127.0.0.1 --browser.gatherUsageStats false
```

**Resultado:** inicialização sem erro, log com URL local e health check
`http://127.0.0.1:8599/_stcore/health` retornando `ok`.
Processo encerrado após a verificação; nova consulta confirmou que a porta não responde.
`git diff --check` passou. Nenhuma alteração em providers, pipelines, scripts ou data.

## Limitações e pendências

- Inspeção visual manual não concluída: o host de acesso ao navegador estava indisponível;
  o acesso ao aplicativo Zen também não foi aprovado pelo controle do computador.
  Não foi tentado contornar essa restrição. Renderização e interações foram verificadas por AppTest.
- AppTest ainda não oferece `select()` para abas: os testes mudam a chave rastreada pelo controle
  `st.tabs(on_change="rerun")`; também testam os botões reais de navegação entre telas.
- Rede e RAG real não foram revalidados: os cenários de sucesso/falha do assistente usam objetos
  controlados; atualização da API foi testada offline. O app reutiliza os snapshots reais existentes.
- A auditoria segue o contrato local de um processo escritor. Não há autenticação de gestores,
  banco transacional multiusuário, envio de mensagens ou concessão de benefício.
- Como previsto no contrato, a estimativa hídrica acadêmica exige validação humana externa.
