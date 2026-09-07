# FisioBase

Sistema web para gestão de um consultório de fisioterapia, desenvolvido como
Projeto Integrador.

## Stack

- **Backend:** Python 3.11 + Flask
- **Banco de dados:** PostgreSQL (Supabase) em produção; SQLite em memória nos testes
- **ORM:** Flask-SQLAlchemy
- **Autenticação:** Flask-Login, com senhas em hash (`werkzeug.security`)
- **Proteção CSRF:** Flask-WTF
- **Front:** HTML/CSS/JavaScript (templates Jinja) e interface React/Vite
- **Testes:** pytest
- **Versionamento:** Git/GitHub
- **Deploy:** Vercel

## Configuração

A aplicação **não sobe** sem estas duas variáveis de ambiente. Isso é
intencional: evita que produção caia silenciosamente num banco local ou use uma
chave de sessão previsível.

| Variável | Descrição |
| --- | --- |
| `SUPABASE_DB_URL` | String de conexão PostgreSQL. Use o **Transaction pooler** do Supabase (porta 6543). |
| `SESSION_SECRET` | Chave usada para assinar o cookie de sessão. |

As variáveis ficam nas configurações de ambiente da plataforma de hospedagem,
nunca em arquivo versionado.

A variável se chama SUPABASE_DB_URL e não DATABASE_URL apontando para o PostgreSQL interno dele, que sobrescreveria
a do Supabase.

> A variável tem nome próprio, e não `DATABASE_URL`, para não colidir com
> variáveis de mesmo nome que alguns ambientes de execução definem
> automaticamente.

> A variável se chama `SUPABASE_DB_URL` e não `DATABASE_URL` porque o Replit
> injeta uma `DATABASE_URL` própria, apontando para o PostgreSQL interno dele,
> que sobrescreveria a do Supabase.

## Executar

```bash
pip install -r requirements.txt
python3 app.py
```

A aplicação usa a porta definida em `PORT`, ou 5000 por padrão.

## Testes

```bash
python3 -m pytest -v
```

São 19 testes cobrindo autenticação, controle de acesso por perfil e os
endpoints JSON. Rodam em **SQLite na memória** — não abrem conexão com o
Supabase e não tocam em dado real.

O que é verificado:

- Login válido para os dois perfis e redirecionamento para o painel correto
- Recusa de senha incorreta, e-mail inexistente e usuário desativado
- Normalização de e-mail (espaços e maiúsculas)
- Bloqueio cruzado de perfil: fisioterapeuta não acessa área administrativa e vice-versa
- Sessão exigida nas rotas protegidas, e encerrada no logout
- Endpoints `/api`, incluindo a garantia de que o hash da senha nunca é serializado

## Banco de dados

O esquema é criado **uma vez**, manualmente, pelo SQL Editor do Supabase.
A aplicação não executa `db.create_all()` nem migrações automáticas: em ambiente
serverless isso rodaria a cada cold start.

Tabelas: `usuarios`, `pacientes`, `ciclos_tratamento`, `grupos`,
`grupo_pacientes`, `agendamentos`, `presencas`, `evolucoes`, `feriados`,
`cartoes`, além da view `vw_relatorio_mensal`.

Row Level Security está habilitado. A aplicação conecta com usuário PostgreSQL,
que passa por cima do RLS — portanto o controle de acesso ao dado clínico é
responsabilidade do código Flask.

### Primeiro usuário

Não há usuário padrão nem seed automático em produção. Para criar o primeiro
administrador, gere o hash e insira no banco:

```python
from werkzeug.security import generate_password_hash
generate_password_hash("sua-senha")
```

```sql
INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo)
VALUES ('Nome', 'email@exemplo.com', 'hash-gerado-acima', 'ADMIN', TRUE);
```

Os demais usuários são criados pela própria aplicação.

## Perfis

| Perfil | Acesso |
| --- | --- |
| `ADMIN` | Painel administrativo e gestão de usuários |
| `FISIOTERAPEUTA` | Painel próprio |

Os valores são gravados em maiúsculo e validados por `CHECK` constraint no banco.

## API de autenticação

- `POST /api/auth/login` — valida credenciais e cria a sessão
- `GET /api/auth/session` — retorna o usuário do cookie de sessão atual
- `POST /api/auth/logout` — encerra a sessão
- `GET /api/admin/users` — lista usuários e totais, apenas para administradores

## Estrutura

```
.
├── app.py                  # fábrica da aplicação, rotas e handlers de erro
├── models.py               # modelos SQLAlchemy
├── requirements.txt
├── pytest.ini
├── tests/
│   ├── conftest.py         # fixtures e SQLite em memória
│   ├── test_auth.py        # autenticação e controle de acesso
│   └── test_api.py         # endpoints JSON
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard_admin.html
│   ├── dashboard_fisioterapeuta.html
│   ├── 403.html
│   └── 404.html
├── static/
│   ├── css/style.css
│   └── js/app.js
└── artifacts/
    └── fisiobase-web/      # interface React/Vite
```

## Pendências conhecidas

- Os endpoints `/api/auth/login` e `/api/auth/logout` estão isentos de CSRF
  porque o front React ainda não envia o token. Os formulários HTML estão
  protegidos. A solução definitiva é o front obter o token e enviá-lo no
  cabeçalho da requisição.
- Módulos clínicos (pacientes, agenda, prontuário, grupos e cartão) ainda não
  implementados; o esquema do banco já os contempla.
- `SESSION_COOKIE_SECURE` precisa ser habilitado antes do deploy em produção.
