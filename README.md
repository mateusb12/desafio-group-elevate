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

Contas demo (senha `demo123`): `admin@elevate.dev` (ADMIN), `ana@logicall.example` (Logicall), `bruno@salesbound.example` (Salesbound), `carla@atendemais.example` (AtendeMais). Não representam integrações reais.

## 5. Aplicação e arquitetura

- [x] Tópico concluído.

Stack e fluxo principal:

- Stack: React/TypeScript → Flask/SQLAlchemy → PostgreSQL.
- Fluxo: formulário → `POST /api/leads` → validação/contato → dispatcher → call center registrado no lead → `POST /api/webhooks/callcenter` → histórico/status → interface.
- Organização do backend: `auth/`, `leads/` e `dispatcher/`.
- A atribuição é persistida no banco.
- Não há filas, Redis ou envio para call centers reais.

## 6–7. Recebimento e validação

- [x] Tópico concluído.

`POST /api/leads` recebe:

- Dados pessoais;
- Produto e funil;
- Origem, campanha e afiliado;
- Parâmetros UTM.

Validações e respostas:

- Pydantic valida tipos, formatos e campos obrigatórios.
- Produto e funil são verificados contra um catálogo definido no código.
- O e-mail normalizado identifica o contato.
- Cada lead recebe ID e horário próprios.
- Dados inválidos retornam `400`.
- Content-Type inadequado retorna `415`.

## 8. Duplicidade e idempotência

- [x] Tópico concluído.

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

- [ ] Tópico parcialmente concluído: faltam migrations e a modelagem de algumas entidades previstas no teste.

Principais tabelas:

- `contacts`: representa a pessoa.
- `leads`: mantém produto, funil, afiliado, origem, destino e status atual.
- `call_centers`: guarda os pesos de distribuição.
- `events`: armazena o histórico.
- `users`: armazena os perfis.

**Estado atual e simplificação consciente:** `Product`, `Funnel`, `Affiliate` e `Distribution` ainda não existem como entidades/tabelas próprias. Produto, funil e afiliado são campos em `leads`, e a distribuição é representada diretamente por `leads.call_center_id`.

**Pendente:** versionar o schema com migrations (o projeto ainda utiliza inicialização automática do schema).

## 10. Índices

- [ ] Tópico pendente: existem apenas índices básicos derivados do ORM e constraints; falta estratégia baseada em consultas e medição.

Há apenas índices básicos declarados no modelo, além dos índices implícitos das PKs e constraints únicas:

- `contacts.email` (UNIQUE);
- `leads.contact_id` (`index=True`);
- `leads.call_center_id` (`index=True`);
- `events.lead_id` (`index=True`);
- `leads.idempotency_key` (UNIQUE);
- `events (lead_id, external_id)` (UNIQUE).

Isso **não representa uma estratégia de índices concluída**. Ainda falta:

- Levantar as consultas reais e seus padrões de filtragem/ordenação.
- Medir os planos com `EXPLAIN ANALYZE`.
- Avaliar índices compostos, como `(call_center_id, received_at)`, quando a filtragem e a paginação forem movidas para o backend.
- Documentar a justificativa de cada índice e evitar adicionar índices sem medição.

## 11. Escalabilidade do banco

- [x] Tópico documentado; as evoluções descritas ainda não estão implementadas.

Estratégia por volume:

- Até 100 mil leads: PostgreSQL e índices direcionados.
- A partir de 1 milhão: filtros e paginação no backend, além de análise dos planos de consulta.
- Acima de 10 milhões: monitoramento do histórico e reavaliação dos gargalos.

Possíveis evoluções:

- Substituir a contagem global do dispatcher por contadores transacionais por centro.
- Avaliar filas e particionamento somente após medir a demanda.

**Nada disso é apresentado como já implementado.**

## 12. Lead Dispatcher

- [x] Tópico concluído.

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

- [x] Tópico concluído.

O dispatcher:

- Usa `pg_advisory_xact_lock(41625, 20261017)` antes de consultar as contagens.
- Mantém o lock até o `COMMIT` da atribuição.
- Impede que duas requisições decidam com base no mesmo estado desatualizado.

**Não é lock do banco inteiro**: apenas as transações que usam essa chave são coordenadas. Os testes verificaram 100 cadastros concorrentes, proporção 50/30/20 e requisições efetivamente esperando o lock no PostgreSQL.

## 14. Webhook do call center

- [x] Tópico concluído.

`POST /api/webhooks/callcenter` aceita:

- `lead_id`;
- `external_id`;
- `status`;
- `event_at` com timezone (`timestamp` no exemplo do PDF; escolhi `event_at` para indicar o horário do acontecimento).

Status aceitos: `new`, `contacted`, `no_answer`, `callback`, `qualified`, `sale`, `refund`, `invalid`.

O evento é registrado no histórico e pode atualizar o status atual.

## 15. Webhook duplicado

- [x] Tópico concluído.

Um acontecimento é identificado por **`(lead_id, external_id)`**:

- Novo evento → `201`.
- Mesmo ID, status e horário → `200` (`duplicate: true`).
- Mesmo ID com dados conflitantes → `409`.

O banco também impõe `UNIQUE(lead_id, external_id)`. O `SELECT ... FOR UPDATE` na linha do lead serializa webhooks do mesmo lead, sem bloquear o processamento de outros leads.

## 16. Eventos fora de ordem

- [x] Tópico concluído.

Eventos inéditos atrasados entram no histórico, mas **só alteram `leads.status` se `event_at` superar o último horário registrado**.

Por exemplo, um `contacted` das 14h não desfaz uma `sale` das 14h30 recebida primeiro. Não impus um stepper rígido entre status.

## 17. Segurança do webhook

- [x] Tópico concluído dentro da estratégia atual; rate limiting ainda não existe.

Controles da integração:

- Usa `X-Webhook-Key`, configurada em `CALLCENTER_WEBHOOK_KEY`.
- Compara a chave com `hmac.compare_digest`.
- Administradores autenticados também podem simular eventos.
- Sem credencial válida, o endpoint rejeita a chamada.
- A chave não deve ficar no frontend.

## 18–19. Dashboard, lista e filtros

- [ ] Tópico parcialmente concluído: dashboard e pesos são demonstrativos, e filtros/paginação ainda são locais.

A lista consulta leads reais por `GET /api/leads`:

- ADMIN vê todos os leads.
- OPERATOR vê apenas os leads do próprio call center, **com restrição no backend**.
- A tela oferece filtros por período, produto, funil, origem, centro e status, mas aplica todos localmente depois de carregar a lista completa.
- A paginação também é local, com cinco itens por página.

**Pendências:** não há endpoint de métricas para o dashboard; a edição de pesos usa somente `localStorage`; não há filtros ou paginação server-side; e não há endpoints para abrir detalhes ou atualizar o status de leads pelo operador.

## 20–22. Autenticação, autorização e segurança

- [ ] Tópico parcialmente concluído: autenticação e autorização básica existem, mas faltam rate limiting e proteção completa contra brute force.

Controles implementados:

- JWT em cookie `HttpOnly`.
- CSRF em operações autenticadas por cookie.
- Logout com revogação no PostgreSQL.
- Senhas armazenadas com hash.
- Access token com duração de 15 minutos.
- Perfil conferido pelo backend nas rotas, sem depender apenas das telas ocultas.

Para produção, ainda seriam necessários HTTPS, `JWT_COOKIE_SECURE=1`, segredo forte e medidas contra tentativas repetidas. **Rate limiting e proteção completa contra brute force não estão implementados.**

## 23. Testes e LAB

- [ ] Tópico parcialmente concluído: há testes de núcleo e concorrência, mas ainda faltam coberturas de APIs e fluxos que não foram implementados.

O LAB:

- Gera até 100 leads com Faker.
- Envia cenários válidos, inválidos, duplicados ou mistos.
- Exibe o HTTP e o resultado esperado.

Os testes existentes cobrem:

- Autenticação;
- Validação;
- Persistência;
- Concorrência do dispatcher;
- Webhook duplicado;
- Webhook fora de ordem;
- `external_id` conflitante.

As suítes de integração também verificam concorrência real no PostgreSQL, incluindo espera por advisory lock do dispatcher e `FOR UPDATE` nos webhooks. Os registros temporários são limpos.

Ainda faltam testes específicos para as APIs de dashboard, configuração do dispatcher, filtros/paginação server-side e atualização de status pelo operador, porque essas APIs ainda não existem.

```bash
docker compose exec -T backend python -m unittest discover -s tests -p 'test_*.py' -v
```

As verificações de persistência usadas nos testes consultam diretamente o PostgreSQL. **Após mudar o contrato de idempotência, é preciso executar novamente a suíte.**

## 27–28. Priorização, limitações e stack

- [ ] Tópico parcialmente concluído: a priorização está documentada, mas há pendências funcionais e de infraestrutura listadas abaixo.

Prioridades da implementação:

- Recebimento;
- Banco de dados;
- Dispatcher concorrente;
- Webhooks.

Stack escolhida por familiaridade e baixo custo operacional: Flask, SQLAlchemy, PostgreSQL, Pydantic, React, TypeScript, Vite, Docker Compose e uv.

Pendências confirmadas na codebase:

- Migrations;
- Modelagem de produto, funil, afiliado e distribuição como entidades, se o escopo exigir esses relacionamentos;
- Estratégia e medição de índices;
- Paginação server-side;
- Filtros server-side;
- Endpoint de métricas do dashboard;
- API persistente para configuração dos pesos;
- Detalhe e atualização de leads para operadores;
- Métricas reais;
- Persistência das configurações de pesos pela interface;
- Testes adicionais de autorização;
- Rate limiting e proteção contra brute force;
- Observabilidade.

Evitei infraestrutura extra sem necessidade comprovada.

## Como usei IA (item 3)

- [x] Tópico concluído.

Usei ChatGPT para discutir alternativas, revisar código e construir testes. Exemplos em que **revisei ou corrigi a saída**:

- Migrei de SQLite para PostgreSQL para coordenar operações concorrentes.
- Comparei sessões Flask e JWT, escolhendo Flask-JWT-Extended em vez de implementar autenticação própria.
- Reduzi abstrações e separei autenticação de autorização.
- Corrigi um teste de expiração que criava o token já expirado, em vez de deixá-lo expirar após login válido.
- Encontrei no LAB uma regressão da validação Pydantic: produtos/funis inexistentes eram aceitos. Corrigi e acrescentei regressão.
- Verifiquei resultados no PostgreSQL, além dos testes e do build Docker.

A IA acelerou o trabalho, mas não foi tratada como validação. Os artefatos de instruções/planos devem acompanhar o histórico Git (item 25).

## Estado real da implementação

Esta tabela foi conferida contra a codebase atual. “Demonstrativo” significa que a tela existe, mas ainda usa dados locais ou simulados; não significa que exista uma API equivalente no backend.

| Área | Situação atual |
| --- | --- |
| Recebimento de leads | Funcional no backend, com validação Pydantic, persistência, contato normalizado e respostas HTTP básicas. |
| Idempotência | Funcional no backend, com `Idempotency-Key`, hash do payload, constraint única e lock por chave. |
| Dispatcher | Funcional no recebimento, com pesos semeados no banco, seleção por déficit ponderado e lock transacional. |
| Webhook | Funcional no backend, com validação, histórico, deduplicação, eventos fora de ordem e proteção por chave/admin. |
| Autenticação | Funcional para login, `/me`, logout, cookies JWT, CSRF e revogação de tokens. |
| Dashboard | Demonstrativo: métricas fixas retornadas por `dashboard.service.ts`; não há endpoint de métricas. |
| Configuração do dispatcher | Demonstrativa: leitura e gravação em `localStorage`; não altera os pesos do banco. |
| Lista de leads | Consulta dados reais, mas filtros e paginação são feitos no React após carregar toda a lista. |
| Atendimento do operador | Ainda não há endpoint/tela para abrir detalhes ou atualizar o status de um lead. |
| Schema e migrations | O schema é criado com `Base.metadata.create_all`; migrations ainda não existem. |
| Índices | Há índices básicos derivados de `index=True`, PKs, FKs e constraints únicas; ainda não há estratégia medida com planos de consulta. |
| Rate limiting e brute force | Não implementados. |
