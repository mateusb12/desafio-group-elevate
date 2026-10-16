# Backend

API Flask organizada por fatias verticais. A autenticação está em `auth/`, com
Blueprint, serviço e entidade ORM próprios. `CallCenter` pertence ao domínio
operacional `dispatcher/`; `database.py` concentra somente a infraestrutura
compartilhada do SQLAlchemy.

## Executar

```bash
python -m pip install -r requirements.txt
JWT_SECRET_KEY=local-demo-only-change-me-with-32-plus-bytes SEED_DEMO=1 python app.py
```

Ou inicie frontend e backend juntos com `docker compose up --build` na raiz do projeto.

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
