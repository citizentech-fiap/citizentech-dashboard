# CitizenTech — Painel de decisão (Front-end e Mobile Development em Sistemas de IA)

> Em construção. Estrutura de camadas exigida pela disciplina:

| Pasta | Responsabilidade |
|---|---|
| `providers/` | acesso a dados externos (HTTP, APIs, leitura bruta) |
| `pipelines/` | limpeza, agregação e enriquecimento dos dados |
| `features/` | telas, cada uma com uma responsabilidade |
| `state/` | estado centralizado (`st.session_state`) |
| `ui/` | componentes visuais reutilizáveis e layout |

## Parte da solução CitizenTech
| Repositório | Disciplina | Papel |
|---|---|---|
| `citizentech-rpa` | AI for RPA | coleta das Cartas de Serviço e pré-triagem dos pedidos |
| `citizentech-genai` | Generative AI | assistente RAG |
| **`citizentech-dashboard`** (este) | Front-end | painel de decisão do gestor |
