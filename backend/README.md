# Backend

API mínima em Flask.

## Executar

```bash
python -m pip install -r requirements.txt
python app.py
```

Ou inicie frontend e backend juntos com `docker compose up --build` na raiz do projeto.

- `GET /` retorna `Hello, world!`
- `GET /ping` retorna `{"status":"ok","message":"pong"}`
