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

## Prioridade 1 — Núcleo funcional

- [ ] **Banco de dados relacional**
  - [ ] Modelar `Lead`, `Product`, `Funnel`, `Affiliate`, `CallCenter`, `Distribution` e histórico/status do lead.
  - [ ] Relacionar leads com produto, funil, origem/afiliado e distribuição.
  - [ ] Versionar alterações de schema com migrations.
  - [ ] Escolher índices a partir das consultas esperadas e documentar o motivo.
- [ ] **Recebimento de leads — `POST /api/leads`**
  - [ ] Validar campos obrigatórios, e-mail, telefone, produto, funil, UTM e tipos recebidos.
  - [ ] Persistir lead e dados de tracking/origem.
  - [ ] Gerar identificador único e registrar data/hora de criação.
  - [ ] Retornar status HTTP e mensagens adequadas para sucesso e dados inválidos.
  - [ ] Definir e documentar tratamento de requisições duplicadas/idempotência.
- [ ] **Dispatcher de leads**
  - [ ] Distribuir entre Call Center A (50%), B (30%) e C (20%), com a estratégia escolhida documentada.
  - [ ] Persistir a distribuição de cada lead.
  - [ ] Garantir consistência com requisições concorrentes, sem condições de corrida.
- [ ] **Webhook — `POST /api/webhooks/callcenter`**
  - [ ] Validar o evento e localizar o lead.
  - [ ] Atualizar status e registrar evento/histórico para auditoria.
  - [ ] Aceitar apenas os status previstos: `new`, `contacted`, `no_answer`, `callback`, `qualified`, `sale`, `refund`, `invalid`.
  - [ ] Evitar processar o mesmo webhook mais de uma vez.
  - [ ] Definir como eventos fora de ordem afetam o status atual e preservar o histórico.
  - [ ] Proteger o endpoint com assinatura HMAC, API key ou estratégia equivalente e documentar a escolha.

## Prioridade 2 — Acesso e acompanhamento

- [ ] **Autenticação e autorização**
  - [ ] Implementar perfil `ADMIN` para visualizar leads/métricas, consultar distribuição e administrar configurações do dispatcher.
  - [ ] Implementar perfil `OPERATOR` associado a um call center.
  - [ ] Restringir operadores aos leads do próprio call center e às ações necessárias ao atendimento.
  - [ ] Verificar permissões no backend em todas as rotas; não depender de ocultar controles no frontend.
- [ ] **Dashboard administrativo**
  - [ ] Exibir total de leads, leads de hoje, distribuídos, pendentes, vendas e taxa de conversão.
  - [ ] Exibir tabela com lead, produto, funil, origem, call center, status e data.
- [ ] **Filtros e paginação**
  - [ ] Filtrar por período, produto, funil, origem, call center e status.
  - [ ] Paginar no backend para não carregar todos os leads no navegador.

## Prioridade 3 — Confiabilidade, segurança e entrega

- [ ] **Testes automatizados**
  - [ ] Unitários para validação, algoritmo de distribuição e regras de transição de status.
  - [ ] Integração para `POST /api/leads` e `POST /api/webhooks/callcenter`.
  - [ ] Concorrência: múltiplas requisições simultâneas e consistência da distribuição.
- [ ] **Segurança da aplicação**
  - [ ] Revisar autenticação, autorização, validação de entrada, SQL injection, XSS e CSRF quando aplicável.
  - [ ] Considerar brute force, rate limiting, exposição de dados sensíveis e segurança dos webhooks.
  - [ ] Documentar proteções implementadas e riscos/limitações conhecidos.
- [ ] **Docker Compose**
  - [ ] Subir frontend, backend, banco de dados e demais serviços realmente usados com `docker compose up`.
  - [ ] Documentar configuração e execução local.
- [ ] **README**
  - [ ] Explicar instalação, execução e como rodar testes.
  - [ ] Descrever arquitetura e fluxo do lead, do recebimento à atualização por webhook.
  - [ ] Registrar decisões técnicas, estratégia de idempotência, concorrência, índices e segurança.
  - [ ] Explicar como a modelagem poderia evoluir de 100 mil para 1 milhão e mais de 10 milhões de leads.
  - [ ] Listar limitações, itens adiados e melhorias futuras.
  - [ ] Relatar como a IA foi usada: ferramentas, tarefas delegadas, sugestões rejeitadas/erros e como o resultado foi validado.
- [ ] **Git e artefatos do desenvolvimento**
  - [ ] Fazer commits incrementais com mensagens que expliquem cada mudança.
  - [ ] Preservar instruções, planos e especificações usados no desenvolvimento.
  - [ ] Não reescrever o histórico antes da entrega.
- [ ] **Entrega**
  - [ ] Confirmar que o repositório contém código, histórico, README, Docker/Compose e testes.
  - [ ] Conferir que outra pessoa consegue executar o projeto seguindo as instruções.

## Preparação para a apresentação técnica

- [ ] Executar a aplicação e preparar demonstração de dispatcher, webhooks, autenticação e testes.
- [ ] Conseguir explicar arquitetura, banco de dados, fluxo do lead e decisões principais.
- [ ] Revisar cenários não implementados e limitações documentadas.
- [ ] Praticar uma pequena alteração no código e explicar como foi feita/validada.

## Critério de priorização

O PDF destaca como núcleo **recebimento de leads, banco de dados, dispatcher com concorrência e webhook**. Se o prazo apertar, priorize essas partes com implementação funcional e bem estruturada; registre explicitamente no README o que ficar pendente e como seria feito depois. A interface pode ser simples.
