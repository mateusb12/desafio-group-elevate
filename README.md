# Group Elevate

## Iniciar frontend e backend

Com Docker Compose instalado, na raiz do projeto rode:

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:5000
- Healthcheck: http://localhost:5000/ping

O frontend consulta `/api/ping` a cada 5 segundos. O proxy do Vite encaminha a chamada para o backend; o Compose espera o healthcheck do backend antes de iniciar o frontend.

O Compose monta os diretórios locais nos containers: alterações no frontend atualizam a página pelo Vite HMR, e alterações no backend reiniciam o servidor Flask automaticamente.

Para encerrar, use `docker compose down`.
