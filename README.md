# FisioBase

Base inicial de um sistema web para um consultório de fisioterapia, criada para
um Projeto Integrador de Desenvolvimento Web.

## Executar

```bash
python app.py
```

A aplicação usa a variável `PORT` quando estiver disponível. O banco SQLite é
criado automaticamente em `instance/fisioterapia.db`.

O artefato web React/Vite usa o backend Flask por meio das rotas `/api/auth/*`.
O Flask mantém a sessão com Flask-Login e o front consulta essa sessão ao abrir
a aplicação; não há usuário autenticado persistido em `localStorage`.

## API de autenticação

- `POST /api/auth/login` — valida `email` e `senha` contra `usuarios` e cria a sessão.
- `GET /api/auth/session` — retorna o usuário associado ao cookie de sessão.
- `POST /api/auth/logout` — encerra a sessão atual.
- `GET /api/admin/users` — lista usuários e totais apenas para administradores.

## Acessos de demonstração

| Perfil | E-mail | Senha |
| --- | --- | --- |
| Admin | admin@fisio.com | Admin@123 |
| Fisioterapeuta | fisio@fisio.com | Fisio@123 |

As senhas são armazenadas somente como hash usando `werkzeug.security`.

## Estrutura inicial

```text
.
├── app.py
├── models.py
├── artifacts/
│   ├── api-server/       # serviço Flask exposto em /api
│   └── fisiobase-web/    # interface React/Vite
├── instance/
│   └── fisioterapia.db
├── templates/
│   ├── 403.html
│   ├── 404.html
│   ├── base.html
│   ├── dashboard_admin.html
│   ├── dashboard_fisioterapeuta.html
│   └── login.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```