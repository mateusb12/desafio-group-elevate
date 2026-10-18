# Elevate Lead Dispatcher

Teste Full Stack do Grupo Elevate. O sistema recebe leads, distribui o atendimento e acompanha os resultados por webhook. As seções seguem **os números dos requisitos do PDF**, agrupando apenas assuntos próximos. Veja também o [checklist](docs/checklist.md).

## Executar (24. Docker)

```bash
docker compose up --build
```

Serviços disponíveis:

- Frontend: <http://localhost:5173>
- API: <http://localhost:5000>
- PostgreSQL: `localhost:5433` (`elevate` / `elevate-local-only`)
- Simuladores HTTP: Logicall (`http://localhost:8101`), Salesbound
  (`http://localhost:8102`) e AtendeMais (`http://localhost:8103`)

Os três simuladores representam APIs externas fictícias para testar a futura
integração com os call centers cadastrados: Logicall (`call-center-a`),
Salesbound (`call-center-b`) e AtendeMais (`call-center-c`). Internamente, os
endpoints são `http://logicall:8101/leads`,
`http://salesbound:8102/leads` e `http://atendemais:8103/leads`; no host,
as mesmas APIs ficam disponíveis nas portas locais 8101, 8102 e 8103.

Depois de iniciar o Compose, teste a saúde e o recebimento de um lead:

```bash
curl http://localhost:8101/health
curl -X POST http://localhost:8101/leads \
  -H 'Content-Type: application/json' \
  -d '{"lead_id":"demo-001","name":"Exemplo"}'
curl -X POST http://localhost:8102/leads \
  -H 'Content-Type: application/json' \
  -d '{"lead_id":"demo-002"}'
curl -X POST http://localhost:8103/leads \
  -H 'Content-Type: application/json' \
  -d '{"lead_id":"demo-003"}'
```

Os simuladores ainda não estão conectados ao dispatcher e não recebem chamadas
do backend durante a criação de leads. Em uma etapa posterior, RabbitMQ e
Transactional Outbox serão introduzidos para encaminhamento assíncrono
confiável.

Pare com `docker compose down`, sem apagar o volume.

No ambiente local, `SEED_DEMO=1` mantém os usuários, centros, produtos, funis,
associações e status demonstrativos disponíveis automaticamente. Para descartar
os dados mockados e repopular tudo no próximo startup, use `RESET_DEMO=1`:

```bash
RESET_DEMO=1 docker compose up --build
```

Esse reset é destrutivo e serve somente para o banco local de demonstração.

Contas demo (senha `demo123`): `admin@elevate.dev` (ADMIN), `ana@logicall.example` (Logicall), `bruno@salesbound.example` (Salesbound), `carla@atendemais.example` (AtendeMais). Não representam integrações reais.

## 5. Aplicação e arquitetura

- [x] Integrar frontend, API e PostgreSQL com atribuição persistida.

Stack e fluxo principal:

- Stack: React/TypeScript → Flask/SQLAlchemy → PostgreSQL.
- Fluxo: formulário → `POST /api/leads` → validação/contato → dispatcher → call center registrado no lead → `POST /api/webhooks/callcenter` → histórico/status → interface.
- Organização do backend: features verticais em `backend/features/` e
  infraestrutura compartilhada em `backend/shared/`.
- A atribuição é persistida no banco.
- Não há filas, Redis ou envio para call centers reais.

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

- [x] Identificar reenvios por Idempotency-Key, com unicidade e proteção concorrente.

A identidade do cadastro vem do header **`Idempotency-Key` (UUID v4)**, criado pelo remetente.

- Nova operação: usa uma chave nova.
- Reenvio: reutiliza a chave original.
- A chave é persistida em `leads.idempotency_key`.
- `payload_hash` compara o conteúdo validado.
- Duas operações distintas podem ter dados iguais, desde que usem chaves diferentes.

| Caso | HTTP | Efeito |
| --- | --- | --- |
| Chave inédita | `201` | Cria lead e distribuição |
| Mesma chave e mesmo payload | `200` | Devolve mesmo ID (`duplicate: true`) |
| Mesma chave, payload diferente | `409` | Rejeita conflito |
| Mesmo payload, chave diferente | `201` | Nova operação legítima |
| Chave ausente/inválida | `400` | Rejeita entrada |

A unicidade da chave é garantida no banco. Um `pg_advisory_xact_lock` derivado do UUID coordena tentativas simultâneas com a mesma chave até `COMMIT`/`ROLLBACK`.

## 9. Banco de dados

- [x] Persistir contatos, leads, call centers, usuários e histórico de eventos.
- [x] Versionar alterações do schema com migrations.
- [x] Modelar Product, Funnel, ProductFunnel, Affiliate, LeadStatus e Distribution como entidades relacionais.

Principais tabelas:

- `contacts`: representa a pessoa.
- `products`: catálogo dos produtos cadastrados.
- `funnels`: catálogo dos funis cadastrados.
- `product_funnels`: associações N:N entre produtos e funis.
- `affiliates`: afiliados externos, criados transacionalmente quando aparecem pela primeira vez.
- `lead_statuses`: catálogo dos status aceitos por leads e eventos.
- `leads`: mantém referências de produto, funil, afiliado, origem, destino e status atual.
- `call_centers`: guarda os pesos de distribuição.
- `events`: armazena o histórico.
- `distributions`: histórico de cada atribuição, incluindo a distribuição inicial.
- `users`: armazena os perfis.
- `token_blocklist`: registra tokens JWT revogados.

O schema é versionado pelas revisions Alembic 001–007. A revisão 002 cria o catálogo
de produtos; as revisions 003–007 adicionam funis, associações produto/funil,
afiliados, status e histórico de distribuições. `leads.call_center_id` continua
representando o destino atual, enquanto `distributions` preserva o histórico.

O modelo atual possui **12 tabelas de aplicação**, além de `alembic_version`.
As revisions Alembic atuais criam as tabelas e constraints; o seed local (`SEED_DEMO=1`)
povoa os catálogos depois de aplicar as migrations. **As revisions regeneradas não
incluem backfill de dados legados.** Para atualizar uma base com dados anteriores,
é necessário planejar a migração desses registros antes de acrescentar as FKs.
Os números de constraints e os testes com backfill divulgados anteriormente
referiam-se à versão anterior das revisions e precisam ser revalidados.

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
- [ ] Reexecutar a suíte completa após a regeneração das migrations e os últimos fluxos de atendimento.
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

Em uma rodada anterior (18/10/2026), passaram 20 testes backend,
além dos testes específicos de 100 leads concorrentes (50/30/20),
50 reenvios idempotentes, criação concorrente de afiliados e webhooks.
**Esses resultados antecedem a regeneração das migrations e os últimos commits**;
a execução completa no estado atual ainda precisa ser confirmada.

**Ainda pendente:** revalidar o schema atual a partir de um PostgreSQL vazio,
executar toda a suíte de regressão e cobrir eventuais condições limite.

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
| Banco e migrations (9) | Concluído; 12 tabelas e revisions 001–007 validadas |
| Índices e escala (10–11) | Parcial; planejamento de escala documentado |
| Dispatcher e webhooks (12–17) | Concluído |
| Interface, segurança e testes (18–23) | Parcial |
| Priorização e evolução (27–28) | Planejado e documentado |

As **checklists de cada seção numerada** são a referência para acompanhar as pendências, sem duplicá-las aqui.
