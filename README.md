# FisioBase

Base inicial de um sistema web para um consultório de fisioterapia, criada para
um Projeto Integrador de Desenvolvimento Web.

## Executar

```bash
python app.py
```

A aplicação usa a variável `PORT` quando estiver disponível. O banco SQLite é
criado automaticamente em `instance/fisioterapia.db`.

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