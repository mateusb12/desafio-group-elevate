# Elevate Lead Dispatcher

Aplicação full stack do desafio técnico do Grupo Elevate. O sistema recebe leads,
associa sua origem, distribui para call centers e acompanha o ciclo de vida do
lead.

Este README acompanha a evolução do desafio: registra o que já foi implementado,
as decisões tomadas e os requisitos ainda pendentes. Ele não representa uma
afirmação de que todas as etapas do PDF já estão concluídas.

## Estado atual

### Implementado

- Frontend React + TypeScript + Vite.
- Backend Flask.
- SQLite com SQLAlchemy ORM.
- Entidades `User` e `CallCenter`, com perfis, vínculo de operador e pesos iniciais de distribuição.
- Organização inicial por fatias verticais no backend.
- Autenticação com dois perfis:
  - `ADMIN`;
  - `OPERATOR`, vinculado a um call center.
- JWT com Flask-JWT-Extended em cookie `HttpOnly` e `SameSite=Lax`.
- Proteção CSRF para requisições que alteram estado.
- Revogação de access tokens no SQLite durante o logout.
- Senhas armazenadas com hash via Werkzeug.
- Blueprint vertical de autenticação:
  - `POST /auth/login`;
  - `GET /auth/me`;
  - `POST /auth/logout`.
- Seed das contas de demonstração:
  - `admin@elevate.dev` / `demo123`;
  - `ana@logicall.example` / `demo123`
  - `bruno@salesbound.example` / `demo123`
  - `carla@atendemais.example` / `demo123`.
- Healthcheck em `GET /ping`.

### Próximas etapas do desafio

- [ ] Modelar `Lead`, `Product`, `Funnel`, `Affiliate`, `Distribution` e histórico de status.
- [ ] Adicionar migrations para versionar o schema.
- [ ] Implementar `POST /api/leads` com validação, identificador e idempotência.
- [ ] Implementar distribuição ponderada para os call centers Logicall/Salesbound/AtendeMais (`50%/30%/20%`).
- [ ] Garantir consistência da distribuição sob concorrência.
- [ ] Implementar `POST /api/webhooks/callcenter`.
- [ ] Tratar webhooks duplicados e eventos fora de ordem.
- [ ] Proteger o webhook com assinatura, API key ou estratégia equivalente.
- [ ] Implementar autorização backend por perfil e escopo de call center.
- [ ] Implementar métricas e dashboard administrativo.
- [ ] Implementar filtros e paginação de leads.
- [ ] Criar testes unitários, de integração e de concorrência.
- [ ] Documentar índices e estratégia para crescimento do volume de leads.

## Arquitetura

O projeto segue uma abordagem vertical: cada domínio deve concentrar seu modelo,
serviços, rotas e testes próximos uns dos outros. A infraestrutura compartilhada
fica separada apenas quando não pertence a um domínio específico.

```text
backend/
├── app.py                  # composição da aplicação e healthcheck
├── database.py             # engine, Base e sessões SQLAlchemy
├── auth/
    ├── __init__.py         # auth_blueprint
    ├── models.py           # entidades User e CallCenter
    ├── routes.py           # endpoints de autenticação
    └── service.py          # autenticação, seed e payload público
└── dispatcher/
    ├── models.py           # entidade CallCenter
    └── __init__.py         # domínio operacional
```

O próximo domínio deve seguir o mesmo formato, por exemplo:

```text
backend/leads/
├── models.py
├── routes.py
├── service.py
└── tests/
```

`User` possui `role`, `is_active`, timestamps e uma chave estrangeira opcional
para `CallCenter`. A regra de domínio é garantida também no banco: `ADMIN` não
possui call center; `OPERATOR` precisa possuir um. A entidade `CallCenter` pertence
ao domínio `dispatcher`, porque participa da distribuição e da configuração
operacional. Os call centers iniciais Logicall/Salesbound/AtendeMais possuem pesos `50/30/20` para a futura
distribuição.

Não foram adicionados fila, worker, cache ou outro serviço neste momento. O PDF
permite esses componentes, mas não os exige; a primeira versão prioriza o caminho
mais simples com Flask e SQLite. Uma decisão diferente será registrada aqui quando
uma necessidade real do domínio justificar a complexidade.

## Decisões técnicas atuais

### Banco e ORM

SQLite foi escolhido para a primeira versão por ser suficiente para o ambiente do
desafio e simples de executar localmente. O acesso é feito por SQLAlchemy ORM, com
consultas parametrizadas e sem SQL construído a partir de entrada do usuário.

O schema ainda não possui migrations. Essa é uma pendência explícita antes de
começar a evoluir os modelos de leads.

### Autenticação

A autenticação usa um access token JWT gerenciado pelo Flask-JWT-Extended. O
navegador recebe o token em cookie `HttpOnly`; o cookie CSRF complementar é lido
pelo frontend apenas para ser enviado no cabeçalho das requisições mutáveis. A
senha nunca é retornada pela API e não é armazenada em texto puro.
`JWT_SECRET_KEY` deve ser definido no ambiente em qualquer execução fora do
cenário local:

```bash
JWT_SECRET_KEY=uma-chave-forte-e-secreta
```

O access token expira por padrão em 15 minutos (`JWT_ACCESS_TOKEN_MINUTES`). Não
há refresh token nesta primeira versão. O logout é efetivo no servidor: o `jti`
do token é salvo em `token_blocklist` e tokens revogados deixam de ser aceitos.

Em produção, também defina `JWT_COOKIE_SECURE=1` para exigir HTTPS nos cookies.

Autenticação e autorização são tratadas como responsabilidades diferentes: a
autenticação atual identifica o usuário; a autorização por perfil e call center
será aplicada nas rotas de leads, dashboard e dispatcher.

### Escalabilidade e concorrência

O PDF pede reflexão sobre volumes de até milhões de leads e concorrência na
distribuição. A implementação dessa parte ainda não começou. Antes de escolher
fila, Redis ou worker, será avaliado se transações e operações atômicas no banco
resolvem o primeiro cenário sem adicionar infraestrutura desnecessária.

## Execução

Com Docker Compose:

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:5000
- Healthcheck: http://localhost:5000/ping

Execução local do backend:

```bash
cd backend
python -m pip install -r requirements.txt
JWT_SECRET_KEY=local-demo-only-change-me-with-32-plus-bytes SEED_DEMO=1 python app.py
```

Execução local do frontend:

```bash
cd frontend
npm install
npm run dev
```

## Critérios de segurança a acompanhar

Conforme o PDF, as próximas implementações devem considerar:

- validação de entrada e mensagens HTTP consistentes;
- SQL Injection, usando ORM/queries parametrizadas;
- autorização no backend, e não apenas ocultação no frontend;
- isolamento dos leads por call center;
- CSRF conforme a estratégia de sessão adotada;
- brute force e rate limiting no login;
- não exposição de hashes e dados sensíveis;
- autenticação e idempotência dos webhooks;
- histórico auditável de alterações de status.

## Testes esperados

A suíte será construída junto com os domínios, priorizando os fluxos críticos do
PDF:

- unitário: validação de lead;
- unitário: algoritmo de distribuição;
- unitário: transições de status;
- integração: `POST /api/leads`;
- integração: `POST /api/webhooks/callcenter`;
- concorrência: múltiplos leads distribuídos simultaneamente.
