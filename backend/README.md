# Backend

API Flask organizada por fatias verticais. A autenticação está em `auth/`, com
Blueprint, serviço e entidade ORM próprios. `CallCenter` pertence ao domínio
operacional `dispatcher/`; `database.py` concentra somente a infraestrutura
compartilhada do SQLAlchemy.

## Executar

```bash
python -m pip install -r requirements.txt
SEED_DEMO=1 python app.py
```

Ou inicie frontend e backend juntos com `docker compose up --build` na raiz do projeto.

- `GET /` retorna `Hello, world!`
- `GET /ping` retorna `{"status":"ok","message":"pong"}`
- `POST /auth/login` autentica e cria a sessão
- `GET /auth/me` retorna o usuário da sessão atual
- `POST /auth/logout` encerra a sessão

Contas demo:

- `admin@elevate.dev` / `demo123`
- `ana@logicall.example` / `demo123`
  - `bruno@salesbound.example` / `demo123`
  - `carla@atendemais.example` / `demo123`
