# FisioBase

Base inicial de um sistema web para gestão de um consultório de fisioterapia, com autenticação e permissões por perfil.

## Run & Operate

- `python app.py` — run the Flask application
- `pnpm run typecheck` — typecheck the existing TypeScript workspace packages
- The Flask app uses `PORT` when provided and defaults to port 8000.
- `SESSION_SECRET` is used as the Flask session secret when provided.

## Stack

- Python 3.11
- Flask 3
- SQLite + Flask-SQLAlchemy
- Flask-Login
- HTML, CSS e JavaScript

## Where things live

- `app.py` — criação da aplicação, rotas e controle de permissões
- `models.py` — configuração do ORM e modelo `usuarios`
- `templates/` — telas de login, dashboards e erros
- `static/` — estilos e comportamento da interface
- `instance/fisioterapia.db` — banco SQLite criado automaticamente

## Architecture decisions

- A autenticação local foi usada porque o briefing acadêmico escolheu explicitamente Flask-Login.
- Senhas nunca são persistidas em texto puro; o modelo usa hash do Werkzeug.
- O controle de acesso é feito por perfil em cada rota protegida, com resposta 403 para perfis incompatíveis.
- A base começa com SQLite para facilitar o desenvolvimento e a evolução posterior.

## Product

- Login com perfis ADMIN e FISIOTERAPEUTA
- Dashboard administrativo com resumo dos usuários
- Dashboard restrito do fisioterapeuta
- Logout e mensagens de acesso
- Base preparada para pacientes, agenda e relatórios

## User preferences

- O usuário solicitou que a primeira etapa fosse interrompida após a base de login para revisar a estrutura antes dos módulos seguintes.

## Gotchas

- O seed cria as contas de demonstração somente quando a tabela `usuarios` está vazia.
- Para redefinir os dados iniciais localmente, remova o arquivo `instance/fisioterapia.db` e reinicie a aplicação.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
