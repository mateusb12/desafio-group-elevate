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
- Produto, funil e a combinação entre ambos são validados nos catálogos do PostgreSQL; somente registros ativos são aceitos.
- O e-mail normalizado identifica o contato.
- Cada lead recebe ID e horário próprios.
- Dados inválidos retornam `400`.
- Content-Type inadequado retorna `415`.

Os catálogos ativos estão disponíveis em `GET /api/products`, `GET /api/funnels` e
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
- `products`: catálogo de produtos ativos e históricos.
- `funnels`: catálogo de funis ativos e históricos.
- `product_funnels`: associações N:N ativas entre produtos e funis.
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

**Estado validado:** 12 tabelas de aplicação, além de `alembic_version`;
32 constraints (14 FKs, 13 PKs, 4 UNIQUE e 1 CHECK) e 23 índices.
A validação foi feita em PostgreSQL descartável com dados legados,
preservação dos registros e `alembic check` sem divergências.

## 10. Índices

- [x] Manter índices básicos e constraints de integridade declarados no ORM.
- [ ] Mapear as consultas reais e seus filtros/ordenação.
- [ ] Medir planos de consulta com EXPLAIN ANALYZE.
- [ ] Avaliar índices compostos com base nas medições.
- [ ] Documentar a justificativa dos índices escolhidos.

Há apenas índices básicos declarados no modelo, além dos índices implícitos das PKs e constraints únicas:

- `contacts.email` (UNIQUE);
- `leads.contact_id` (`index=True`);
- `leads.call_center_id` (`index=True`);
- `events.lead_id` (`index=True`);
- `leads.idempotency_key` (UNIQUE);
- `events (lead_id, external_id)` (UNIQUE);
- `distributions (lead_id, assigned_at)` para histórico de atribuições.

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

Essa abordagem mantém a proporção mais estável em amostras pequenas do que sorteios independentes. A edição dos pesos na interface ainda é demonstrativa.

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
- [ ] Criar API de leitura e alteração dos pesos de distribuição.
- [ ] Conectar a configuração de pesos ao backend, substituindo localStorage.
- [ ] Implementar filtros no backend.
- [ ] Implementar paginação no backend.
- [ ] Criar consulta de detalhes e atualização de status para operadores.

A lista consulta leads reais por `GET /api/leads`:

- ADMIN vê todos os leads.
- OPERATOR vê apenas os leads do próprio call center, **com restrição no backend**.
- A tela oferece filtros por período, produto, funil, origem, centro e status, mas aplica todos localmente depois de carregar a lista completa.
- A paginação também é local, com cinco itens por página.

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
- [x] Reexecutar os testes após as mudanças de idempotência e migrations 001–007.
- [ ] Ampliar testes de autorização e isolamento por call center.
- [ ] Adicionar testes das APIs de métricas, pesos, filtros e atendimento quando criadas.

O LAB:

- Gera até 100 leads com Faker usando produtos, funis e associações reais do PostgreSQL.
- Envia cenários válidos, inválidos, duplicados ou mistos.
- Exibe o HTTP e o resultado esperado.

Os testes existentes cobrem:

- Autenticação;
- Validação;
- Persistência e backfill de dados legados;
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

As verificações de persistência usadas nos testes consultam diretamente o PostgreSQL. **Validação final das migrations 001–007 (18/10/2026):** 12 testes de integração, 5 de autenticação/autorização
e 5 unitários passaram. Também foram validados 100 leads concorrentes (50/30/20),
50 reenvios idempotentes (1 criação e 49 duplicatas), 20 requisições usando
o mesmo afiliado (um único cadastro) e webhooks concorrentes/fora de ordem.
O LAB consultou os catálogos reais, o Compose temporário inicializou
o backend após as migrations e `/ping` respondeu 200. Build do frontend aprovado;
lint sem erros, com 1 warning preexistente em `LabWebhooksPage.tsx`.
Os recursos Docker temporários foram descartados.

**Ainda pendente:** ampliar a suíte conforme surgirem as APIs de dashboard,
pesos, filtros e atendimento; reforçar cenários de isolamento por call center.

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

Usei ChatGPT para discutir alternativas, revisar código e construir testes. Exemplos em que **revisei ou corrigi a saída**:

- Migrei de SQLite para PostgreSQL para coordenar operações concorrentes.
- Comparei sessões Flask e JWT, escolhendo Flask-JWT-Extended em vez de implementar autenticação própria.
- Reduzi abstrações e separei autenticação de autorização.
- Corrigi um teste de expiração que criava o token já expirado, em vez de deixá-lo expirar após login válido.
- Encontrei no LAB uma regressão da validação Pydantic: produtos/funis inexistentes eram aceitos. Corrigi e acrescentei regressão.
- Verifiquei resultados no PostgreSQL, além dos testes e do build Docker.

A IA acelerou o trabalho, mas não foi tratada como validação. Os artefatos de instruções/planos devem acompanhar o histórico Git (item 25).

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
