# Checklist do desafio técnico

Baseada no [Teste para Dev Fullstack V2.pdf](./Teste%20para%20Dev%20Fullstack%20V2.pdf). Use esta lista para acompanhar a implementação e registrar decisões. O PDF é a referência original caso algum detalhe precise ser conferido.

## Base do projeto

- [x] Criar o repositório Git e publicar uma versão inicial privada.
- [x] Criar o frontend com React, TypeScript, Vite, Tailwind CSS e tema escuro/claro.
- [x] Criar o backend Flask com `GET /` e `GET /ping`.
- [x] Criar Dockerfiles e Compose para iniciar frontend e backend.
- [x] Configurar healthcheck do backend e indicador de conexão no frontend.
- [x] Configurar live reload para frontend e backend no Compose.
- [x] Documentar como iniciar e encerrar o ambiente local.

## Etapa 1 — O que o usuário precisa conseguir fazer no frontend

Começar pelas telas e fluxos abaixo usando dados de exemplo. Depois, conectar cada ação à API e substituir os dados temporários.

- [x] **Acesso**
  - [x] O usuário deve conseguir entrar e sair da aplicação (contas demonstrativas em memória).
  - [x] Depois de entrar, o usuário deve ver as opções permitidas para seu perfil (`ADMIN` ou `OPERATOR`).
- [x] **Administrador (`ADMIN`): acompanhar leads**
  - [x] O administrador deve poder ver um resumo com total de leads, leads recebidos hoje, leads distribuídos, leads pendentes, vendas e taxa de conversão (valores demonstrativos).
  - [x] O administrador deve poder listar todos os leads em uma tabela com nome, produto, funil, origem, call center, status e data de recebimento.
  - [x] O administrador deve poder filtrar a lista por período, produto, funil, origem, call center e status.
  - [x] O administrador deve poder navegar pelos resultados paginados (paginação local dos dados demonstrativos).
  - [x] O administrador deve poder consultar para qual call center cada lead foi distribuído.
  - [x] O administrador deve poder consultar e alterar as configurações do dispatcher (em memória).
- [x] **Operador (`OPERATOR`): atender leads**
  - [x] O operador deve poder ver somente os leads encaminhados ao call center ao qual pertence (filtro demonstrativo no frontend).
  - [x] O operador deve poder abrir um lead e consultar as informações necessárias para o atendimento.
  - [x] O operador deve poder atualizar o status do lead durante o atendimento (em memória).
  - [x] O operador não deve ver telas ou ações administrativas nem acessar leads de outros call centers na interface demonstrativa.
- [x] **Comportamento das telas**
  - [x] O usuário deve receber feedback enquanto os dados carregam e quando uma ação dá certo ou falha.
  - [x] O usuário deve ver estados claros para lista vazia e erro de carregamento.
  - [x] Validar os fluxos com dados de exemplo antes de conectar à API; depois remover/substituir os dados temporários.

## Etapa 2 — Núcleo funcional da API (prioridade técnica indicada no PDF)

- [x] **Banco de dados relacional**
  - [x] Modelar `Lead`, `Product`, `Funnel`, `Affiliate`, `CallCenter`, `Distribution` e histórico/status do lead.
  - [x] Relacionar leads com produto, funil, origem/afiliado e distribuição.
  - [x] Versionar alterações de schema com migrations.
  - [x] Escolher índices a partir das consultas esperadas e documentar o motivo.
- [x] **Recebimento de leads — `POST /api/leads`**
  - [x] Validar campos obrigatórios, e-mail, telefone, produto, funil, UTM e tipos recebidos.
  - [x] Persistir lead e dados de tracking/origem.
  - [x] Gerar identificador único e registrar data/hora de criação.
  - [x] Retornar status HTTP e mensagens adequadas para sucesso e dados inválidos.
  - [x] Definir e documentar tratamento de requisições duplicadas/idempotência.
- [x] **Dispatcher de leads**
  - [x] Distribuir entre Logicall (50%), Salesbound (30%) e AtendeMais (20%), com a estratégia escolhida documentada.
  - [x] Persistir a distribuição de cada lead.
  - [x] Garantir consistência com requisições concorrentes, sem condições de corrida.
- [x] **Webhook — `POST /api/webhooks/callcenter`**
  - [x] Validar o evento e localizar o lead.
  - [x] Atualizar status e registrar evento/histórico para auditoria.
  - [x] Aceitar apenas os status previstos: `new`, `contacted`, `no_answer`, `callback`, `qualified`, `sale`, `refund`, `invalid`.
  - [x] Evitar processar o mesmo webhook mais de uma vez.
  - [x] Definir como eventos fora de ordem afetam o status atual e preservar o histórico.
  - [x] Proteger o endpoint com assinatura HMAC, API key ou estratégia equivalente e documentar a escolha.

## Etapa 2 — Contas, permissões e integração com a API

- [x] **Autenticação e autorização**
  - [x] Implementar perfil `ADMIN` para visualizar leads/métricas, consultar distribuição e administrar configurações do dispatcher.
  - [x] Implementar perfil `OPERATOR` associado a um call center.
  - [x] Restringir operadores aos leads do próprio call center e às ações necessárias ao atendimento.
  - [x] Verificar permissões no backend em todas as rotas; não depender de ocultar controles no frontend.
- [x] **API para as telas**
  - [x] Disponibilizar as métricas e os dados usados pelo dashboard.
  - [x] Disponibilizar listagem paginada com os filtros usados na tela de leads.
  - [x] Disponibilizar consulta de distribuição e leitura/alteração das configurações do dispatcher para administradores.
  - [x] Disponibilizar consulta e atualização de status dos leads permitidos para operadores.
  - [x] Conectar as telas feitas na etapa 1 à API e remover os dados temporários.

## Etapa 3 — Confiabilidade, segurança e entrega

- [x] **Testes automatizados**
  - [x] Unitários para validação, algoritmo de distribuição e regras de transição de status.
  - [x] Integração para `POST /api/leads` e `POST /api/webhooks/callcenter`.
  - [x] Concorrência: múltiplas requisições simultâneas e consistência da distribuição.
- [ ] **Segurança da aplicação**
  - [x] Revisar autenticação, autorização, validação de entrada, SQL injection, XSS e CSRF quando aplicável.
  - [ ] Considerar brute force, rate limiting, exposição de dados sensíveis e segurança dos webhooks.
  - [x] Documentar proteções implementadas e riscos/limitações conhecidos.
- [x] **Docker Compose**
  - [x] Subir frontend, backend, banco de dados e demais serviços realmente usados com `docker compose up`.
  - [x] Documentar configuração e execução local.
- [x] **README**
  - [x] Explicar instalação, execução e como rodar testes.
  - [x] Descrever arquitetura e fluxo do lead, do recebimento à atualização por webhook.
  - [x] Registrar decisões técnicas, estratégia de idempotência, concorrência, índices e segurança.
  - [x] Explicar como a modelagem poderia evoluir de 100 mil para 1 milhão e mais de 10 milhões de leads.
  - [x] Listar limitações, itens adiados e melhorias futuras.
  - [x] Relatar como a IA foi usada: ferramentas, tarefas delegadas, sugestões rejeitadas/erros e como o resultado foi validado.
- [x] **Git e artefatos do desenvolvimento**
  - [x] Fazer commits incrementais com mensagens que expliquem cada mudança.
  - [x] Preservar instruções, planos e especificações usados no desenvolvimento.
  - [x] Não reescrever o histórico antes da entrega.
- [x] **Entrega**
  - [x] Confirmar que o repositório contém código, histórico, README, Docker/Compose e testes.
  - [x] Conferir que outra pessoa consegue executar o projeto seguindo as instruções.

## Preparação para a apresentação técnica

- [ ] Executar a aplicação e preparar demonstração de dispatcher, webhooks, autenticação e testes.
- [ ] Conseguir explicar arquitetura, banco de dados, fluxo do lead e decisões principais.
- [ ] Revisar cenários não implementados e limitações documentadas.
- [ ] Praticar uma pequena alteração no código e explicar como foi feita/validada.

## Critério de priorização

O PDF destaca como núcleo **recebimento de leads, banco de dados, dispatcher com concorrência e webhook**. Se o prazo apertar, priorize essas partes com implementação funcional e bem estruturada; registre explicitamente no README o que ficar pendente e como seria feito depois. A interface pode ser simples.
