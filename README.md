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
- Quando o call center confirma o recebimento, o worker salva a entrega no
  PostgreSQL e confirma a mensagem no RabbitMQ.
- Se houver uma falha temporária, o worker salva a próxima tentativa no
  PostgreSQL antes de confirmar a mensagem. Depois, o scheduler tenta de novo.
- Falhas definitivas são encaminhadas para a fila `lead.distributed.invalid`.
- O estado da entrega fica salvo em `delivery_leads_to_call_centers`.
- Cada simulador guarda os `event_id` em SQLite, usando um volume Docker.
- O worker reconhece eventos já entregues e evita novos envios HTTP. Se o
  simulador receber o mesmo `event_id` novamente, responde `duplicate=true`
  sem repetir o efeito.

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

Escolhi o RabbitMQ para separar o cadastro do lead do envio aos call centers.
Assim, se um serviço externo estiver fora do ar, o lead ainda pode ser salvo.
A Outbox guarda o envio pendente, o RabbitMQ separa as etapas e o Delivery
Worker tenta fazer a entrega em segundo plano. Essa escolha facilita os testes
de recuperação, mas também aumenta a complexidade da aplicação.

### Evolução arquitetural: Outbox transacional e Delivery Worker

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

Se o RabbitMQ estiver fora do ar, a entrega continua pendente até o serviço
voltar. Se o call center voltar antes de esgotar as tentativas, a entrega será
retomada automaticamente. Caso contrário, a mensagem permanece na fila de
falhas para reprocessamento futuro.

Como pode haver reenvios, o fluxo usa a estratégia **at-least-once**. O worker
e os serviços fictícios verificam o `event_id` para evitar que o mesmo evento
de entrega produza efeitos duplicados.

Para testar as falhas, pare um dos serviços, crie um lead e ligue o serviço
novamente. O envio será retomado se ainda houver tentativas disponíveis. Caso
contrário, a mensagem ficará na fila de falhas. Se a mesma mensagem for
enviada mais de uma vez, a resposta será `duplicate=true`.

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
- `outbox_pending_deliveries`: envios que ainda precisam ser processados.
- `delivery_leads_to_call_centers`: situação de cada entrega.

O banco usa 11 migrations Alembic, da `d86498fb27a3` até a revisão atual
`f1a2b3c4d5e6`. A última migration adiciona quatro índices de performance,
definidos após análise das consultas reais com `EXPLAIN (ANALYZE, BUFFERS)`.

O PostgreSQL possui 14 tabelas de aplicação, além de `alembic_version`. Os três
simuladores usam SQLite para guardar os `event_id` que já receberam e evitar
entregas repetidas.

No ambiente local, o seed cria os dados de demonstração depois que as migrations
terminam. A atualização de um banco antigo ainda precisa de um plano próprio
para migrar os dados existentes.

## 10. Índices

- [x] Manter índices básicos e constraints de integridade declarados no ORM.
- [x] Mapear as consultas reais e seus filtros/ordenação.
- [x] Medir planos com `EXPLAIN (ANALYZE, BUFFERS)` em banco de teste.
- [x] Criar índices adicionais somente quando houve ganho mensurável.
- [x] Documentar a justificativa dos índices escolhidos.

Foram analisadas as consultas do dispatcher, da lista de leads, do dashboard,
dos webhooks, da Outbox, dos retries e do histórico de distribuições.

Os índices atuais já atendem às buscas por chave primária, e-mail, idempotência,
call center, contato, evento e distribuição. A migration `f1a2b3c4d5e6` adiciona:

- `(leads.received_at DESC, leads.id DESC)` para a ordenação da listagem;
- índice parcial `(created_at, id)` da Outbox somente para `published_at IS NULL`;
- índice parcial `(next_retry_at, event_id)` para retries vencidos;
- índice parcial `(failed_at, event_id)` para falhas sem confirmação de DLQ.

Resultado do benchmark com 50 mil leads, 100 mil eventos e 50 mil registros de
Outbox/entrega:

| Consulta | Tempo antes | Tempo depois | Plano utilizado | Decisão |
| --- | ---: | ---: | --- | --- |
| Dispatcher: contagem por call center | 16,35 ms | 19,18 ms | `Seq Scan` + `HashAggregate` | Manter; três grupos justificam a leitura |
| Lista de leads, página 51 | 26,26 ms | 5,04 ms | `Index Scan` + joins por índice | Criar índice de ordenação |
| Dashboard: contagem total | 5,43 ms | 5,81 ms | `Seq Scan` + `Aggregate` | Manter |
| Dashboard: agrupamento por status | 24,12 ms | 24,37 ms | `Seq Scan` + `HashAggregate` | Manter |
| Webhook: `(lead_id, external_id)` | 0,12 ms | 0,06 ms | `Index Scan` na constraint única | Índice existente suficiente |
| Histórico de eventos do lead | 0,08 ms | 0,08 ms | `Bitmap Scan` + sort pequeno | Não criar índice composto |
| Outbox: 10 pendentes mais antigos | 6,96 ms | 0,08 ms | `Index Only Scan` parcial | Criar índice parcial |
| Worker: 8 retries vencidos | 18,83 ms | 0,19 ms | índice parcial + `Nested Loop` | Criar índice parcial |
| Worker: 8 falhas sem DLQ | 17,84 ms | 0,15 ms | índice parcial + `Nested Loop` | Criar índice parcial |
| Histórico de distribuição do lead | 0,06 ms | 0,06 ms | `Index Scan Backward` existente | Índice existente suficiente |

Os tempos são de uma execução no banco temporário e podem variar um pouco. O
`Seq Scan` do dispatcher e do dashboard foi mantido porque, nesse volume, ler
as linhas diretamente foi uma boa escolha do PostgreSQL.

Também foi testado um índice composto para `call_center_id`, `status` e a
ordenação da listagem. Ele reduziu a página filtrada de 16,20 ms para 0,17 ms,
mas piorou a contagem exata da mesma requisição de 30,68 ms para 59,94 ms.
Como o endpoint executa as duas operações, o índice não foi mantido. Nesse caso,
o problema pode estar na forma de fazer a paginação e a contagem, não na falta
de outro índice.

## 11. Escalabilidade do banco

- [x] Documentar a evolução prevista para 100 mil, 1 milhão e mais de 10 milhões de leads.

O benchmark mostrou que a lista ordenada, a Outbox e as filas de retry precisavam
de índices próprios. Ele não mede o comportamento com concorrência e tráfego de
produção.

Até 100 mil leads, PostgreSQL com esses índices deve atender bem. Perto de 1
milhão, é importante acompanhar o tempo da listagem, da contagem, dos lotes da
Outbox, dos retries e o tempo de espera do dispatcher. A paginação atual usa
`OFFSET/LIMIT`, que fica mais lenta em páginas muito profundas. Se isso virar um
problema, a primeira alternativa a testar é paginação por cursor usando
`(received_at, id)`.

Em 10 milhões de leads, também devem ser acompanhados o tamanho de `events` e
`distributions`, o uso de disco, o crescimento dos índices e o tempo de
`COUNT(*)`. Particionamento por data ou limpeza do histórico só deve ser avaliado
se esses números mostrarem um problema real.

O dispatcher pode virar um gargalo porque cada distribuição espera sua vez no
advisory lock e faz uma nova contagem. Isso ainda não foi um problema comprovado
no benchmark. Se a espera crescer, a primeira alternativa a medir é guardar
contadores por call center junto com a distribuição.

Na Outbox e no scheduler, os índices parciais evitam procurar no histórico já
processado. Ainda assim, é importante acompanhar a quantidade de pendências, a
idade do item mais antigo e a quantidade de retries.



## 12. Lead Dispatcher

- [x] Distribuir e persistir leads com déficit ponderado (50/30/20).

Pesos atuais:

- Logicall: **50%**;
- Salesbound: **30%**;
- AtendeMais: **20%**.

Em cada cadastro, o algoritmo:

1. Compara quantos leads cada call center recebeu com a proporção esperada.
2. Escolhe o maior **déficit ponderado** (o call center que mais está abaixo
   da sua proporção esperada).
3. Grava o `call_center_id` escolhido.

Assim, a distribuição fica mais próxima de 50/30/20 mesmo com poucos leads.
Os pesos alterados na tela são salvos no backend e usados nas próximas
distribuições.

## 13. Concorrência

- [x] Evitar decisões erradas quando vários leads chegam ao mesmo tempo.
- [x] Testar a distribuição com 100 cadastros simultâneos.

Imagine uma fila na porta do dispatcher. Antes de escolher o call center, cada
http request espera sua vez, consulta os números atuais do banco e salva sua decisão. 

A fila é criada com `pg_advisory_xact_lock` e dura até a transação terminar.

Esse lock protege apenas a **decisão de distribuição**: 
- consultar as quantidades
- escolher o call center
- salvar o resultado. 

O lock não trava uma tabela inteira, não trava uma linha específica ou o banco inteiro. 
Todas as outras operações continuam funcionando
normalmente.

Os testes confirmaram que 100 leads concorrentes mantêm a proporção 50/30/20 e
que algumas requisições realmente esperam sua vez no PostgreSQL.

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

Chave de idempotência: **`(lead_id, external_id)`**:

- Novo evento → `201`.
- Mesmo ID, status e horário → `200` (`duplicate: true`).
- Mesmo ID com dados conflitantes → `409`.

O banco não deixa o mesmo evento entrar duas vezes: cada combinação de
`lead_id` e `external_id` precisa ser única. Quando dois webhooks do mesmo lead
chegam juntos, eles entram numa pequena fila exclusiva desse lead. Enquanto um
é processado, o outro espera; webhooks de outros leads continuam normalmente.

## 16. Eventos fora de ordem

- [x] Persistir eventos atrasados sem regredir o status atual.

Um evento pode chegar atrasado e ainda assim fica salvo no histórico. Porém, o
status atual só muda quando o evento é mais recente que o último status salvo.

Por exemplo: se uma venda das 14h30 chegar primeiro, um contato das 14h não
vai fazer o lead voltar no passado. Os status também não precisam seguir uma
ordem fixa.

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

- O ADMIN pode ver todos os leads.
- Cada OPERATOR vê apenas os leads do seu call center.
- É possível filtrar a lista por período, produto, funil, origem, call center,
  status e texto de busca.
- A lista é dividida em páginas e mostra o total de resultados.
- `GET /api/leads/<id>` mostra os dados do lead e seu histórico.
- `PATCH /api/leads/<id>/status` altera o status e registra essa mudança no
  histórico.
- Se um operador tentar acessar um lead de outro call center, o sistema não
  permite e retorna `404`.

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

Validações finais:

**Instalação limpa**

- Ambiente Docker Compose inicializado com volumes novos e PostgreSQL vazio.
- Migrations aplicadas até a revisão vigente naquele teste.
- API e serviços inicializados corretamente.
- Suíte completa: **56 testes aprovados**.
- Ambiente temporário removido, preservando os dados de desenvolvimento.

**Otimização de índices**

- Benchmark isolado com 50 mil leads, 100 mil eventos e dados relacionados.
- Consultas avaliadas com `EXPLAIN (ANALYZE, BUFFERS)`.
- Quatro índices adicionados após comparação de desempenho.
- Migration `f1a2b3c4d5e6` validada com upgrade, downgrade e novo upgrade.
- Suíte completa executada novamente após as alterações: **56 testes aprovados em 9,092 segundos**.
- `git diff --check` sem erros.

A instalação limpa foi validada com PostgreSQL vazio, incluindo a última migration
de índices, e o Docker Compose foi iniciado novamente nesse estado.

## 27–28. Priorização, limitações e stack

- [x] Entregar primeiro as partes principais do sistema.
- [ ] Adicionar monitoramento mais completo no futuro.

O que foi feito primeiro:

- recebimento dos leads;
- banco de dados;
- distribuição dos leads;
- webhooks.

Escolhi Flask, SQLAlchemy, PostgreSQL, Pydantic, React, TypeScript, Vite,
Docker Compose e uv porque já conheço essas ferramentas e elas atendem ao
projeto sem aumentar a complexidade.

Não adicionei serviços extras sem uma necessidade clara.

### Limitações conhecidas e próximas evoluções

- **Limite de tentativas:** ainda não há proteção contra muitas tentativas de
  login ou contra excesso de requisições. No futuro, usaria Flask-Limiter com
  Redis compartilhado entre as instâncias da API. O login teria limites por IP
  e por conta; leads e webhooks teriam limites por cliente ou credencial. Quem
  ultrapassasse o limite receberia HTTP `429`.
- **Mensagens que não foram entregues:** elas ficam guardadas, mas ainda não há
  uma tela para tentar o envio novamente. Se todas as tentativas acabarem, a
  mensagem vai para a fila de falhas, mas o reprocessamento ainda não é
  automático. Isso pode ser adicionado depois, com controle de acesso e
  histórico das tentativas.
- **Call center fora do ar:** o lead não é enviado automaticamente para outro
  call center. Essa troca precisa seguir uma regra de negócio definida.
- **Crescimento do sistema:** antes de mudar a forma de distribuição, é preciso
  medir o desempenho com um volume muito maior de leads.
- **Segurança para produção:** ainda é preciso configurar HTTPS, cookies seguros
  e gerenciamento adequado das senhas e chaves.
- **Monitoramento:** o LAB mostra o que acontece no fluxo, mas uma versão de
  produção também precisaria de métricas, alertas e acompanhamento contínuo.

## Como usei IA (item 3)

- [x] Registrar como a IA foi usada no projeto.

Usei o ChatGPT para discutir a arquitetura e revisar decisões. Usei o Codex
para ajudar na implementação, nas refatorações e nos testes. Não aceitei as
sugestões automaticamente: comparei cada uma com o enunciado, o código e os
resultados dos testes.

Algumas decisões em que fiz essa revisão:

- **Mantive os modelos dentro do escopo.** Questionei a criação do campo
  `is_active` em produtos, funis, afiliados e status, porque o desafio não
  pedia esse tipo de controle. Simplifiquei os modelos e refiz as migrations
  que ainda estavam em desenvolvimento, em vez de criar outra migration só
  para desfazer uma complexidade.
- **Melhorei o teste de concorrência.** Várias threads rodando juntas não
  provam, sozinhas, que houve disputa real. Por isso, usei uma `Barrier` para
  sincronizar as requisições e conferi se algumas transações realmente
  esperaram o lock do PostgreSQL.
- **Comparei o LAB com o banco.** Quando a tela mostrava sucesso, conferi se o
  lead realmente tinha sido salvo no PostgreSQL ao invés de confiar na palavra da IA. Também verifiquei as respostas
  HTTP, a idempotência e os efeitos no banco, em vez de confiar apenas na tela.
- **Separei melhor o dispatcher.** A lógica de lock, contagem e escolha do
  call center estava concentrada em uma função grande. Separei essas partes em
  funções menores, como `lock_call_center_distribution`,
  `count_leads_by_call_center` e `select_call_center`.
- **Evitei complicar o frontend.** Questionei abstrações que não ajudavam no
  desafio, mantive a organização por funcionalidades e corrigi interpretações
  literais demais de algumas ideias usadas para descrever a interface.

Para validar o resultado, revisei diffs e consultas, comparei o LAB com o
PostgreSQL e rodei os testes automatizados. Também validei concorrência,
idempotência, migrations e o build do frontend. O histórico de commits mostra
as mudanças e as correções feitas ao longo do projeto.

A IA foi usada como apoio, não como prova de que algo funcionava. A prova veio
do código executado, dos dados salvos e dos testes aprovados.

Não usei arquivos persistentes de instruções como `AGENTS.md` ou `CLAUDE.md`.
Por isso, não criei esses arquivos depois do projeto pronto. As decisões e os
artefatos realmente usados ficaram registrados no Git.

## Visão geral

| Área (itens do PDF) | Situação |
| --- | --- |
| Arquitetura, recebimento e idempotência (5–8) | Concluído |
| Banco e migrations (9) | Concluído; 14 tabelas e 11 migrations Alembic |
| Índices e escala (10–11) | Concluído; 4 índices adicionados após benchmark |
| Dispatcher e webhooks (12–17) | Concluído |
| Interface, segurança e testes (18–23) | Parcial; testes aprovados, proteções adicionais documentadas |
| Priorização e evolução (27–28) | Planejado e documentado |

As **checklists de cada seção numerada** são a referência para acompanhar as pendências, sem duplicá-las aqui.
