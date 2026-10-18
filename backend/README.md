# Backend

API Flask organizada por fatias verticais. A autenticação está em `auth/`, com
Blueprint, serviço e entidade ORM próprios. `CallCenter` pertence ao domínio
operacional `dispatcher/`; `database.py` concentra somente a infraestrutura
compartilhada do SQLAlchemy.

## Executar

```bash
uv sync --locked
DATABASE_URL=postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate JWT_SECRET_KEY=local-demo-only-change-me-with-32-plus-bytes SEED_DEMO=1 uv run python app.py
```

Para rodar diretamente, primeiro inicie o banco com `docker compose up -d db` e
aplique as migrations abaixo. No Docker Compose, o serviço `migrations` executa
`alembic upgrade head` automaticamente antes de iniciar a API.

## Migrations

O schema do banco é gerenciado pelo Alembic. Depois de iniciar o PostgreSQL,
aplique as migrations antes de iniciar a API:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate uv run alembic upgrade head
```

Se o banco já existia antes da adoção do Alembic e foi criado pelo
`create_all`, não execute a migration inicial diretamente: confirme primeiro
que o schema está compatível e marque a revisão atual como aplicada:

```bash
DATABASE_URL=postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate uv run alembic stamp head
```

Esse comando é apenas para a transição da base legada. Em bases novas, use
`upgrade head`.

Para criar uma migration após alterar os modelos:

```bash
DATABASE_URL=postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate uv run alembic revision --autogenerate -m "descreva a alteração"
```

O `alembic.ini` fica em `backend/` e os scripts ficam em
`backend/migrations/`; as dependências continuam declaradas no
`pyproject.toml`, que é o local correto para a instalação do pacote.

- `GET /` retorna `Hello, world!`
- `GET /ping` retorna `{"status":"ok","message":"pong"}`
- `POST /auth/login` autentica e cria o cookie JWT
- `GET /auth/me` retorna o usuário do token atual
- `POST /auth/logout` revoga o token atual

Variáveis relevantes:

- `JWT_SECRET_KEY`: chave de assinatura, obrigatória fora do ambiente local;
- `JWT_ACCESS_TOKEN_MINUTES`: expiração do access token (15 por padrão);
- `JWT_COOKIE_SECURE=1`: exige HTTPS para os cookies, recomendado em produção.

Contas demo:

- `admin@elevate.dev` / `demo123`
- `ana@logicall.example` / `demo123`
  - `bruno@salesbound.example` / `demo123`
  - `carla@atendemais.example` / `demo123`
