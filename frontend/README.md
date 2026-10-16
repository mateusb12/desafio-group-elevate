# Frontend

Aplicação React com TypeScript, Vite e Tailwind CSS v4. A tela inicial usa o tema escuro e permite alternar para o tema claro.

## Desenvolvimento

```bash
npm install
npm run dev
```

O Vite inicia o servidor local e atualiza a página automaticamente durante o desenvolvimento.

Para iniciar frontend e backend juntos com Docker, rode `docker compose up --build` na raiz do projeto. O indicador da tela mostra o resultado de `GET /ping` e consulta novamente a cada 5 segundos.
