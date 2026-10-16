# Elevate Lead Dispatcher

Projeto do teste técnico do Grupo Elevate. A ideia é simples: quando alguém preenche um formulário de vendas, o sistema recebe o contato (lead), identifica de onde ele veio, escolhe um call center para atendê-lo e acompanha o resultado.

Este README registra o que já funciona e as decisões tomadas até aqui. O restante do escopo está no [checklist do desafio](docs/checklist.md).

## Como executar

Com Docker instalado, na raiz do projeto (frontend, API e PostgreSQL):

```bash
docker compose up --build
```

- Interface: http://localhost:5173
- API: http://localhost:5000
- PostgreSQL local: `localhost:5433` (usuário e banco: `elevate`; senha de desenvolvimento: `elevate-local-only`)

Para parar, use `docker compose down`. O volume do PostgreSQL é preservado; `down -v` apagaria os dados.

### Contas para testar

O Docker Compose inicializa estes usuários, todos com a senha `demo123`:

| Nome | E-mail | Acesso |
| --- | --- | --- |
| Rafael | `admin@elevate.dev` | Administrador |
| Ana | `ana@logicall.example` | Operadora da Logicall |
| Bruno | `bruno@salesbound.example` | Operador da Salesbound |
| Carla | `carla@atendemais.example` | Operadora da AtendeMais |

São contas e operações **de demonstração**, sem integração com empresas reais.

## Como o sistema deve funcionar

O fluxo completo, quando implementado, será este:

1. Uma página de vendas envia o cadastro para `POST /api/leads`.
2. A API valida os dados, registra produto, funil e origem e evita cadastros duplicados indevidos.
3. O dispatcher escolhe um call center e salva a distribuição. A configuração inicial é Logicall 50%, Salesbound 30% e AtendeMais 20%.
4. O call center informa o andamento pelo webhook `POST /api/webhooks/callcenter`. O sistema guarda o histórico, inclusive quando chegam eventos repetidos ou fora de ordem.
5. O administrador acompanha os números e os leads. Cada operador acessa apenas os leads do próprio call center.

**O que já está funcionando:** login, identificação do usuário autenticado e logout usando a API e o PostgreSQL. Há perfis de administrador e operador associados aos call centers. A interface de dashboard, lista de leads e configuração de pesos já existe, mas ainda utiliza dados de exemplo.

**O que ainda é demonstração:** os leads exibidos não vêm do banco; a tela de distribuição salva percentuais no navegador (`localStorage`), não altera os pesos do backend; o dispatcher ainda não distribui leads. O isolamento por call center na API de leads também não está implementado.

## Escolhas técnicas

- **Flask e SQLAlchemy:** uma API pequena com modelos relacionais, sem camadas extras antes de elas serem necessárias.
- **PostgreSQL:** permite coordenar atualizações simultâneas com transações e locks por linha, algo importante para o dispatcher. Continua simples de executar pelo Compose.
- **React, TypeScript e Vite:** interface separada da API, com um proxy de desenvolvimento para as chamadas `/api`.
- **Docker Compose:** frontend e backend sobem com um comando, sem exigir configuração manual de serviços adicionais.
- **JWT com Flask-JWT-Extended:** escolhi uma biblioteca conhecida em vez de escrever assinatura e validação de tokens por conta própria. Não implementei refresh token nesta etapa.

O backend está organizado em módulos pequenos, como `auth/` e `dispatcher/`. Não adicionei Redis, filas ou workers só por precaução: primeiro quero medir a necessidade ao resolver a distribuição concorrente.

## Segurança

A autenticação usa JWT em cookie `HttpOnly`, proteção CSRF para operações que alteram dados e revogação de tokens no logout, registrada no PostgreSQL. As senhas são armazenadas com hash. O access token expira em 15 minutos por padrão, sem renovação automática.

O Compose usa uma chave JWT **apenas para desenvolvimento**. Fora do ambiente local, é necessário configurar uma `JWT_SECRET_KEY` forte; em HTTPS, ativar `JWT_COOKIE_SECURE=1`. Os usuários e a senha `demo123` não devem ser disponibilizados num ambiente real.

Ainda falta verificar as permissões nas futuras rotas de leads e dispatcher, autenticar os webhooks e revisar riscos como tentativas repetidas de login e exposição de dados. Esconder uma tela no React não substitui autorização no backend.

## Testes

Em vez de testar cada função isoladamente, comecei pelos comportamentos observáveis da API. Os cinco testes de integração atuais exercitam login, `/auth/me`, CSRF, logout, revogação de JWT, expiração, credenciais inválidas e usuários inativos, usando um banco PostgreSQL separado, criado e apagado automaticamente pelos testes.

Para executar:

```bash
docker compose run --build --rm -T \
  -e PYTHONDONTWRITEBYTECODE=1 \
  backend python -m unittest discover -s tests -p 'test_*.py' -v
```

Quando o núcleo de leads estiver pronto, também vou cobrir validação, distribuição, webhooks duplicados ou fora de ordem e uma bateria de requisições concorrentes. As regras críticas podem receber testes unitários pontuais; o importante é comprovar o comportamento, não aumentar a contagem de testes.

## Volume de dados e concorrência

O PDF propõe começar com 100 mil leads e pensar em 1 milhão e mais de 10 milhões. Não precisamos construir essa infraestrutura agora, mas precisamos justificar como o sistema poderia evoluir.

Minha abordagem inicial é manter o banco relacional, paginar consultas na API e definir índices a partir dos filtros realmente usados (como data, status e call center). Quando os modelos e consultas estiverem prontos, vou registrar quais índices foram escolhidos e por quê.

Para 100 leads chegando quase ao mesmo tempo, a distribuição terá de ser persistida de modo consistente, com transações ou operações atômicas comprovadas por teste. O PostgreSQL dá as ferramentas para coordenar transações concorrentes, mas a distribuição ainda precisará ser implementada de forma atômica e validada sob carga. Redis, filas e particionamento só entram se houver necessidade demonstrada. **Isso é um plano, não uma capacidade já implementada.**

## Limitações e próximos passos

A prioridade agora é completar o núcleo do teste: migrations do PostgreSQL, modelagem, recebimento de leads com idempotência, dispatcher com concorrência e webhook com histórico e proteção contra eventos indevidos. Depois conectarei as telas à API real, com filtros, paginação e autorização por perfil e call center.

Para uma segunda versão, avaliaria melhorias de operação e escala a partir dos resultados: renovação de sessão, observabilidade, processamento assíncrono e ajustes de banco, se fizerem sentido. Prefiro registrar uma limitação a apresentar uma funcionalidade incompleta como se estivesse pronta.

## Como usei IA

Usei o ChatGPT para discutir alternativas, revisar código e montar mudanças pontuais. As escolhas e validações ficaram comigo. Alguns exemplos concretos:

- Migrei do SQLite para PostgreSQL antes de criar o dispatcher, para trabalhar com transações e locks por linha na etapa de concorrência. O antigo arquivo SQLite não foi apagado.
- Comecei com sessões do Flask. Depois comparei essa opção com JWT e optei por Flask-JWT-Extended, mantendo cookies e revogação no banco, sem Redis ou refresh token.
- Pedi uma revisão para cortar redundâncias e evitar abstrações sem benefício. Também mantive a separação entre autenticação (quem é o usuário) e autorização (o que ele pode acessar).
- Um teste de expiração criado com auxílio da IA falhou porque gerava um token já expirado durante o login. Corrigi o cenário para expirar **depois** de um login bem-sucedido.
- A validação encontrou problemas locais de permissões em `__pycache__` e dependências do frontend. Usei testes e build no Docker para validar sem acrescentar mecanismos ao produto.

Os resultados atuais foram conferidos com testes de integração, lint e build. Vou continuar registrando decisões, erros e sugestões rejeitadas conforme as próximas funcionalidades forem implementadas. Os artefatos de instruções e planos utilizados no desenvolvimento também precisam ser preservados no repositório antes da entrega.
