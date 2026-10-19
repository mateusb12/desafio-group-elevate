# Elevate Lead Dispatcher

Teste Full Stack do Grupo Elevate. O sistema recebe leads, distribui o atendimento e acompanha os resultados por webhook. As seções seguem **os números dos requisitos do PDF**, agrupando apenas assuntos próximos. Veja também o [checklist](docs/checklist.md).

## Executar (24. Docker)

```bash
docker compose up --build
```

Serviços disponíveis:

- Frontend: <http://localhost:5173>
- API: <http://localhost:5000>
- PostgreSQL: `localhost:5433` (`user: elevate`, `password: elevate-local-only`)
- RabbitMQ Management UI: <http://localhost:15672> (`user: elevate`,
  `password: elevate-local-only` por padrão)
- Simuladores HTTP: Logicall (`http://localhost:8101`), Salesbound
  (`http://localhost:8102`) e AtendeMais (`http://localhost:8103`)

Os três simuladores representam APIs externas fictícias para testar a
integração com os call centers cadastrados:

- Logicall (`call-center-a`): `http://logicall:8101/leads`;
- Salesbound (`call-center-b`): `http://salesbound:8102/leads`;
- AtendeMais (`call-center-c`): `http://atendemais:8103/leads`.

Depois de iniciar o Compose, teste a saúde e o recebimento de um lead:

```bash
curl http://localhost:8101/health
curl -X POST http://localhost:8101/leads \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"event-demo-001","lead_id":"demo-001"}'
curl -X POST http://localhost:8102/leads \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"event-demo-002","lead_id":"demo-002"}'
curl -X POST http://localhost:8103/leads \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"event-demo-003","lead_id":"demo-003"}'
```

O fluxo automático é **API → Outbox PostgreSQL → Outbox Service → RabbitMQ →
Delivery Worker → POST `/leads`**.

- O worker escolhe o endpoint pelo `call_center_id`.
- A mensagem só é confirmada depois de uma resposta HTTP 2xx.
- O estado da entrega é salvo em `delivery_leads_to_call_centers`.
- Cada simulador guarda os `event_id` em SQLite, usando um volume Docker.
- Se a mesma mensagem for reenviada, o simulador responde `duplicate=true` sem
  repetir a entrega.

Se a entrega der errado, o worker tenta de novo. Mensagens inválidas ou que
continuarem dando erro vão para a fila `lead.distributed.invalid`.

No ambiente local, o projeto já sobe com dados de demonstração. Para apagar
esses dados e criar tudo de novo, use `RESET_DEMO=1`:

```bash
RESET_DEMO=1 docker compose up --build
```

Esse reset é destrutivo e serve somente para o banco local de demonstração.

Contas demo — todas usam a senha `demo123`:

- `admin@elevate.dev` (ADMIN);
- `ana@logicall.example` (Logicall);
- `bruno@salesbound.example` (Salesbound);
- `carla@atendemais.example` (AtendeMais).

Essas contas não representam integrações reais.

## 5. Aplicação e arquitetura

- [x] Integrar frontend, API e PostgreSQL com atribuição persistida.

Stack e fluxo principal:

- Stack: React/TypeScript → Flask/SQLAlchemy → PostgreSQL.
- Fluxo: formulário → `POST /api/leads` → validação/contato → dispatcher → call center registrado no lead → `POST /api/webhooks/callcenter` → histórico/status → interface.
- Organização do backend: features verticais em `backend/features/` e
  infraestrutura compartilhada em `backend/shared/`.
- O call center escolhido fica salvo no banco.
- O envio é feito em segundo plano pelo RabbitMQ, Outbox Service e Delivery
  Worker.
- Logicall, Salesbound e AtendeMais são serviços fictícios usados para testar
  o envio dos leads.

### Evolução arquitetural: Outbox transacional e Delivery Worker

### Como funciona o envio

Quando um lead é criado, o sistema salva uma entrega pendente em
`outbox_pending_deliveries`. Essa gravação acontece junto com o lead e a
distribuição. Se algo der errado, nenhuma dessas informações é salva.

A tabela `events` guarda o histórico do lead. Já a Outbox guarda os envios que
ainda precisam ser processados. Ela armazena apenas os IDs necessários, sem
dados pessoais.

O envio acontece nesta ordem:

1. A entrega é salva na Outbox.
2. O Outbox Service publica a mensagem na fila `lead.distributed` do RabbitMQ.
3. O Delivery Worker envia o lead para o call center escolhido.
4. O sistema atualiza o status da entrega no banco.

Se o RabbitMQ estiver fora do ar, a entrega continua pendente e o retry irá acontecer novamente depois. Como pode haver reenvios, o fluxo usa a estratégia
**at-least-once**. O worker e os serviços fictícios verificam o `event_id` para
evitar que o mesmo lead seja processado duas vezes.

Para testar as falhas, pare um dos serviços, crie um lead e ligue o serviço
novamente. O envio pendente será retomado. Se a mesma mensagem for enviada
mais de uma vez, a resposta será `duplicate=true`.

## 6–7. Recebimento e validação

- [x] Receber, validar e persistir leads, incluindo rastreamento e respostas HTTP.

`POST /api/leads` recebe:

- Dados pessoais;
- Produto e funil;
- Origem, campanha e afiliado;
- Parâmetros UTM.

Validações e respostas:

- Pydantic valida tipos, formatos e campos obrigatórios.
- Produto, funil e a combinação entre ambos são validados pelos catálogos e relacionamentos do PostgreSQL.
- O e-mail normalizado identifica o contato.
- Cada lead recebe ID e horário próprios.
- Dados inválidos retornam `400`.
- Content-Type inadequado retorna `415`.

Os catálogos estão disponíveis em `GET /api/products`, `GET /api/funnels` e
`GET /api/product-funnels`. Afiliados externos inéditos são cadastrados
transacionalmente ao receber o lead.

## 8. Duplicidade e idempotência

- [x] Evitar cadastros duplicados quando o mesmo lead é enviado novamente.

O sistema usa o header **`Idempotency-Key` (UUID v4)** para identificar cada
cadastro. Quem envia o lead deve criar uma chave para cada novo cadastro e
reutilizar essa mesma chave quando precisar tentar de novo.

- A chave fica salva em `leads.idempotency_key`.
- O sistema compara os dados enviados para confirmar se o reenvio é o mesmo.
- Dois cadastros podem ter os mesmos dados, desde que usem chaves diferentes.

| Situação | HTTP | Resultado |
| --- | --- | --- |
| Chave nova | `201` | Cria o lead e a distribuição |
| Mesma chave e mesmos dados | `200` | Retorna o mesmo ID (`duplicate: true`) |
| Mesma chave e dados diferentes | `409` | Retorna conflito |
| Mesmos dados e chave diferente | `201` | Cria outro lead |
| Chave ausente ou inválida | `400` | Rejeita a requisição |

O banco não permite repetir a mesma chave. Se duas requisições usarem a mesma
chave ao mesmo tempo, o PostgreSQL organiza a ordem de processamento para
evitar duplicação.

## 9. Banco de dados

- [x] Salvar contatos, leads, call centers, usuários e histórico de eventos.
- [x] Controlar as mudanças do banco com migrations.

Principais tabelas:

- `contacts`: dados de contato.
- `leads`: dados do lead e seu status atual.
- `products` e `funnels`: catálogos usados nos cadastros.
- `product_funnels`: liga produtos aos funis disponíveis.
- `affiliates`: afiliados informados nos leads.
- `lead_statuses`: status aceitos pelo sistema.
- `call_centers`: call centers e seus pesos de distribuição.
- `events`: histórico de alterações do lead.
- `distributions`: histórico dos call centers escolhidos.
- `users`: usuários e perfis de acesso.
- `token_blocklist`: tokens que foram revogados.

O banco usa dez migrations Alembic, da `d86498fb27a3` até a atual
`c5d7e9f1a2b3`. Elas criam o schema, os catálogos, o histórico de distribuição
e as tabelas usadas no envio dos leads.

Hoje existem **12 tabelas principais** no PostgreSQL, além da tabela usada pelo
Alembic. Os serviços de envio também usam SQLite para guardar seu próprio estado.

No ambiente local, o seed cria os dados de demonstração depois que as migrations
terminam. A atualização de um banco antigo ainda precisa de um plano próprio
para migrar os dados existentes.

## 10. Índices

- [x] Manter índices básicos e constraints de integridade declarados no ORM.
- [x] Mapear as consultas reais e seus filtros/ordenação.
- [ ] Medir planos de consulta com EXPLAIN ANALYZE.
- [ ] Avaliar índices compostos com base nas medições.
- [x] Documentar a justificativa dos índices escolhidos.

Há apenas índices básicos declarados no modelo, além dos índices implícitos das PKs e constraints únicas:

- `contacts.email` (UNIQUE);
- `leads.contact_id` (`index=True`);
- `leads.call_center_id` (`index=True`);
- `events.lead_id` (`index=True`);
- `leads.idempotency_key` (UNIQUE);
- `events (lead_id, external_id)` (UNIQUE);
- `distributions (lead_id, assigned_at)` para histórico de atribuições.

As consultas principais são `GET /api/leads`, que filtra por busca, período,
produto, funil, origem, call center e status, ordena por `received_at` e `id`
e pagina no banco; `GET /api/dashboard/metrics`, que agrega leads por período
e status; e a consulta do histórico de `distributions` por lead e data. Os
índices de chaves estrangeiras apoiam os joins e filtros por relacionamento,
as constraints UNIQUE evitam duplicidades e o índice composto de
`distributions` apoia a ordenação do histórico por lead. Índices compostos
adicionais só serão considerados depois de medir os planos reais.

## 11. Escalabilidade do banco

- [x] Documentar a evolução prevista para 100 mil, 1 milhão e mais de 10 milhões de leads.

Estratégia por volume:

- Até 100 mil leads: PostgreSQL e índices direcionados.
- A partir de 1 milhão: filtros e paginação no backend, além de análise dos planos de consulta.
- Acima de 10 milhões: monitoramento do histórico e reavaliação dos gargalos.

Possíveis evoluções:

- Substituir a contagem global do dispatcher por contadores transacionais por centro.
- Avaliar filas e particionamento somente após medir a demanda.

Para volumes acima de 10 milhões, a próxima etapa seria medir os planos com
`EXPLAIN ANALYZE`, avaliar paginação por cursor nas listas, acompanhar o
crescimento de `events` e `distributions` e investigar a contenção do advisory
lock do dispatcher. Particionamento por data só seria considerado se essas
medições justificassem a complexidade.

**Nada disso é apresentado como já implementado.**

## 12. Lead Dispatcher

- [x] Distribuir e persistir leads com déficit ponderado (50/30/20).

Pesos atuais:

- Logicall: **50%**;
- Salesbound: **30%**;
- AtendeMais: **20%**.

Em cada cadastro, o algoritmo:

1. Compara a quantidade atual de leads com a quantidade esperada após a próxima atribuição.
2. Escolhe o maior **déficit ponderado**.
3. Grava o `call_center_id` escolhido.

Essa abordagem mantém a proporção mais estável em amostras pequenas do que sorteios independentes. A edição dos pesos na interface é persistida pelo backend e usada pelo dispatcher real.

## 13. Concorrência

- [x] Proteger a decisão do dispatcher com advisory lock transacional.
- [x] Validar concorrência real com 100 cadastros.

O dispatcher:

- Usa `pg_advisory_xact_lock(41625, 20261017)` antes de consultar as contagens.
- Mantém o lock até o `COMMIT` da atribuição.
- Impede que duas requisições decidam com base no mesmo estado desatualizado.

**Não é lock do banco inteiro**: apenas as transações que usam essa chave são coordenadas. Os testes verificaram 100 cadastros concorrentes, proporção 50/30/20 e requisições efetivamente esperando o lock no PostgreSQL.

## 14. Webhook do call center

- [x] Validar webhooks, registrar histórico e atualizar o status quando aplicável.

`POST /api/webhooks/callcenter` aceita:

- `lead_id`;
- `external_id`;
- `status`;
- `event_at` com timezone (`timestamp` no exemplo do PDF; escolhi `event_at` para indicar o horário do acontecimento).

Status aceitos: `new`, `contacted`, `no_answer`, `callback`, `qualified`, `sale`, `refund`, `invalid`.

O evento é registrado no histórico e pode atualizar o status atual.

## 15. Webhook duplicado

- [x] Deduplicar eventos por (lead_id, external_id) e tratar conflitos.

Um acontecimento é identificado por **`(lead_id, external_id)`**:

- Novo evento → `201`.
- Mesmo ID, status e horário → `200` (`duplicate: true`).
- Mesmo ID com dados conflitantes → `409`.

O banco também impõe `UNIQUE(lead_id, external_id)`. O `SELECT ... FOR UPDATE` na linha do lead serializa webhooks do mesmo lead, sem bloquear o processamento de outros leads.

## 16. Eventos fora de ordem

- [x] Persistir eventos atrasados sem regredir o status atual.

Eventos inéditos atrasados entram no histórico, mas **só alteram `leads.status` se `event_at` superar o último horário registrado**.

Por exemplo, um `contacted` das 14h não desfaz uma `sale` das 14h30 recebida primeiro. Não impus um stepper rígido entre status.

## 17. Segurança do webhook

- [x] Proteger o webhook com API key ou autenticação administrativa.

Controles da integração:

- Usa `X-Webhook-Key`, configurada em `CALLCENTER_WEBHOOK_KEY`.
- Compara a chave com `hmac.compare_digest`.
- Administradores autenticados também podem simular eventos.
- Sem credencial válida, o endpoint rejeita a chamada.
- A chave não deve ficar no frontend.

## 18–19. Dashboard, lista e filtros

- [x] Listar leads reais com filtros e paginação demonstrativos no frontend.
- [x] Criar endpoint de métricas reais para o dashboard.
- [x] Criar API de leitura e alteração dos pesos de distribuição.
- [x] Conectar a configuração de pesos ao backend, substituindo localStorage.
- [x] Implementar filtros no backend.
- [x] Implementar paginação no backend.
- [x] Criar consulta de detalhes e atualização de status para operadores.

A lista consulta leads reais por `GET /api/leads`:

- ADMIN vê todos os leads.
- OPERATOR vê apenas os leads do próprio call center, **com restrição no backend**.
- A tela envia os filtros por período, produto, funil, origem, centro, status e busca para o backend.
- A API aplica paginação no banco e devolve metadados com total de leads e páginas.
- `GET /api/leads/<id>` retorna os dados do lead e o histórico de eventos.
- `PATCH /api/leads/<id>/status` atualiza o status e registra um novo evento na mesma transação.
- O backend restringe consulta e alteração de operadores ao próprio call center; leads fora do escopo retornam `404`.

## 20–22. Autenticação, autorização e segurança

- [x] Autenticar com JWT/CSRF e validar permissões por perfil no backend.
- [ ] Implementar rate limiting e proteção contra brute force.
- [ ] Preparar configurações seguras de produção (HTTPS, cookie Secure, segredo forte).

Controles implementados:

- JWT em cookie `HttpOnly`.
- CSRF em operações autenticadas por cookie.
- Logout com revogação no PostgreSQL.
- Senhas armazenadas com hash.
- Access token com duração de 15 minutos.
- Perfil conferido pelo backend nas rotas, sem depender apenas das telas ocultas.

## 23. Testes e LAB

- [x] Cobrir autenticação, validação, dispatcher e cenários concorrentes de webhook.
- [x] Reexecutar a suíte completa após a regeneração das migrations e os últimos fluxos de atendimento.
- [x] Testar bloqueio de leitura e alteração de leads de outro call center.
- [x] Adicionar testes das APIs de métricas, pesos e filtros.
- [x] Adicionar testes de detalhe, atualização de status e isolamento por call center.

O LAB:

- Gera até 100 leads com Faker usando produtos, funis e associações reais do PostgreSQL.
- Envia cenários válidos, inválidos, duplicados ou mistos.
- Exibe o HTTP e o resultado esperado.

Os testes existentes cobrem:

- Autenticação;
- Validação;
- Persistência e integridade referencial;
- Validação de produtos, funis e associações;
- Afiliados criados concorrentemente sem duplicação;
- Histórico de distribuições por lead;
- Concorrência do dispatcher;
- Webhook duplicado;
- Webhook fora de ordem;
- `external_id` conflitante.

As suítes de integração também verificam concorrência real no PostgreSQL, incluindo espera por advisory lock do dispatcher e `FOR UPDATE` nos webhooks. Os registros temporários são limpos.

```bash
docker compose exec -T backend python -m unittest discover -s tests -p 'test_*.py' -v
```

Validação final executada em 18/10/2026:

- `docker compose up --build -d`: build e inicialização do Compose concluídos;
- `docker compose exec -T backend python -m unittest discover -s tests -p 'test_*.py' -v`: **56 testes aprovados**;
- migrations aplicadas e `alembic current`: `c5d7e9f1a2b3 (head)`;
- concorrência real: 100 leads com distribuição 50/30/20, 50 reenvios idempotentes e contenção observada no advisory lock;
- frontend: TypeScript e build Vite aprovados;
- smoke tests: `/ping` da API e health checks dos três simuladores aprovados.

A execução acima validou a atualização do schema no banco local do Compose; uma
execução adicional partindo de um volume PostgreSQL vazio continua sendo uma
checagem operacional recomendada antes de um deploy novo.

## 27–28. Priorização, limitações e stack

- [x] Priorizar o núcleo e justificar a stack sem infraestrutura desnecessária.
- [ ] Opcional: adicionar observabilidade conforme a necessidade medida.

Prioridades da implementação:

- Recebimento;
- Banco de dados;
- Dispatcher concorrente;
- Webhooks.

Stack escolhida por familiaridade e baixo custo operacional: Flask, SQLAlchemy, PostgreSQL, Pydantic, React, TypeScript, Vite, Docker Compose e uv.

Evitei infraestrutura extra sem necessidade comprovada.

### Limitações conhecidas e próximas evoluções

- **Rate limiting e brute force (não implementados):** priorizaria os endpoints
  de autenticação, recebimento de leads e webhooks. Em múltiplas instâncias,
  usaria Flask-Limiter com armazenamento compartilhado em Redis, retornando
  `429` e `Retry-After`. No login, combinaria limites por IP e por conta; na
  API de leads, por cliente ou credencial de integração. Os limites seriam
  calibrados com tráfego real e testes de recuperação após o bloqueio.
- **DLQ:** falhas definitivas ficam preservadas, mas ainda não há redrive
  automático. Uma evolução seria oferecer reprocessamento administrativo,
  com auditoria e limite de tentativas.
- **Redistribuição:** se um call center ficar offline, o lead não muda
  automaticamente de destino. Isso depende de regras de negócio explícitas
  para evitar duplicidade ou perda de atribuição.
- **Escalabilidade:** o dispatcher usa advisory lock transacional; a contenção
  precisa ser medida sob volumes muito maiores antes de trocar a estratégia.
- **Segurança de produção:** ainda exigem atenção HTTPS, cookies `Secure`,
  gerenciamento de segredos e configuração apropriada de deploy.
- **Observabilidade:** o LAB demonstra métricas e estados do fluxo, mas não
  substitui métricas de produção, alertas, tracing e monitoramento operacional.

## Como usei IA (item 3)

- [x] Documentar decisões, correções, limitações e validações realizadas com IA.

Usei ChatGPT para discutir arquitetura e revisar decisões, e Codex como apoio à implementação, refatoração e testes. Meu processo não foi aceitar automaticamente a primeira solução: comparei sugestões com o enunciado, examinei o código e confrontei o resultado com testes e dados persistidos.

**Exemplos concretos de revisão e decisões próprias:**

- **Evitei modelagem além do escopo.** Questionei a inclusão generalizada de `is_active` em produtos, funis, afiliados e status porque o enunciado não exigia esse ciclo de vida. Simplifiquei os modelos e regenerei migrations que ainda estavam em elaboração, em vez de acrescentar outra revision só para desfazer complexidade desnecessária.
- **Questionei o teste de concorrência.** Uma execução com várias threads, por si só, não prova disputa simultânea. Pedi uma barreira de sincronização (`Barrier`) e evidência de transações efetivamente esperando o advisory lock do PostgreSQL; o teste de integração passou a verificar essa contenção.
- **Confrontei o LAB com o banco.** Ao observar resultados positivos na interface sem os registros esperados no PostgreSQL, sinalizei falsos positivos e exigi checagens do HTTP, da idempotência e dos efeitos reais, em vez de confiar apenas na indicação visual de sucesso.
- **Refatorei para facilitar a explicação.** Pedi que a lógica do dispatcher deixasse de concentrar lock, contagens e escolha do destino numa função extensa. O código foi separado em funções com nomes descritivos, como `lock_call_center_distribution`, `count_leads_by_call_center` e `select_call_center`.
- **Controlei a complexidade do frontend.** Questionei soluções e abstrações que não ajudavam o desafio, preferi organização por features e corrigi interpretações literais demais de analogias usadas para descrever interações da interface.

**Como validei:** inspecionei diffs e queries, confrontei o LAB com o PostgreSQL e executei testes automatizados (incluindo concorrência e idempotência), migrations em ambiente isolado e verificações de build. O histórico de commits registra a evolução incremental e as correções. As conversas com o Codex foram usadas como apoio, não como evidência de que algo funcionava.

Não utilizei arquivos persistentes de instruções como `AGENTS.md` ou `CLAUDE.md`. Por isso não criei esses arquivos retroativamente; registro aqui as decisões relevantes e mantenho no Git os artefatos de desenvolvimento efetivamente utilizados.

## Visão geral

| Área (itens do PDF) | Situação |
| --- | --- |
| Arquitetura, recebimento e idempotência (5–8) | Concluído |
| Banco e migrations (9) | Concluído; 12 tabelas e 10 revisions Alembic validadas |
| Índices e escala (10–11) | Parcial; planejamento de escala documentado |
| Dispatcher e webhooks (12–17) | Concluído |
| Interface, segurança e testes (18–23) | Parcial |
| Priorização e evolução (27–28) | Planejado e documentado |

As **checklists de cada seção numerada** são a referência para acompanhar as pendências, sem duplicá-las aqui.
