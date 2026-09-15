# Arquitetura

## Visão geral

O FisioBase é uma aplicação web monolítica em Flask, servida em ambiente
serverless pela Vercel, com banco PostgreSQL gerenciado pelo Supabase.

```
Navegador
    │  HTTPS
    ▼
Vercel (@vercel/python)
    │  index.py → create_app()
    ▼
Aplicação Flask
    ├── Flask-Login  ....... sessão e identidade
    ├── Flask-WTF ......... proteção CSRF
    ├── Jinja2 ............ renderização das páginas
    └── Flask-SQLAlchemy .. acesso ao banco
    │  postgresql:// (Transaction pooler, porta 6543)
    ▼
Supabase (PostgreSQL)
```

O front é renderizado no servidor. O JavaScript no navegador cuida apenas de
detalhes de interface: mostrar ou ocultar a senha e fazer os avisos flutuantes
desaparecerem. Os gráficos usam Chart.js carregado por CDN.

## Camadas

| Camada | Arquivo | Responsabilidade |
| --- | --- | --- |
| Entrada | `index.py` | Expõe a aplicação para a Vercel |
| Configuração | `app.py` → `create_app()` | Lê variáveis de ambiente, inicializa extensões e registra rotas |
| Rotas e regras | `app.py` → `register_routes()` | Valida entrada, aplica regras de negócio e decide a resposta |
| Domínio | `models.py` | Modelos, relacionamentos e regras de acesso ao registro |
| Apresentação | `templates/` | Páginas Jinja que herdam de `base.html` |
| Persistência | Supabase | Esquema, chaves estrangeiras e restrições de integridade |

## Fluxo de uma requisição

Exemplo: o fisioterapeuta registra a evolução de uma sessão.

1. O navegador envia `POST /agendamentos/42/evolucao` com o token CSRF.
2. O Flask-WTF valida o token; sem ele, a requisição é recusada.
3. O decorador `@login_required` verifica a sessão; sem ela, redireciona ao login.
4. A rota carrega o agendamento. Se não existir, devolve 404.
5. A função `_acao_evolucao()` decide o que o usuário pode fazer: registrar,
   editar, ver ou nada. Sem permissão, devolve 403.
6. A função `_motivo_bloqueio_evolucao()` verifica se a sessão aceita evolução:
   não pode ser falta, cancelamento nem data futura.
7. Os dados são validados. Se algo estiver errado, o formulário é devolvido com
   status 400 e uma mensagem.
8. A evolução é gravada e, se a sessão ainda estava agendada, passa a realizada.
9. O usuário é redirecionado para a ficha, com um aviso de confirmação.

O mesmo padrão se repete nas demais rotas: **autenticar, autorizar, validar,
gravar, redirecionar**.

## Decisões técnicas

### Por que o esquema não é criado pela aplicação

A aplicação não roda `db.create_all()` nem migrações automáticas. Em ambiente
serverless, cada requisição pode iniciar um processo novo, e isso executaria a
criação do esquema repetidamente. O esquema foi criado uma vez pelo SQL Editor
do Supabase, e alterações são aplicadas manualmente.

### Por que a aplicação recusa subir sem as variáveis

Se faltar `SUPABASE_DB_URL` ou `SESSION_SECRET`, a aplicação levanta
`RuntimeError`. Não existe fallback para SQLite. A alternativa seria pior:
a produção subiria conectada a um banco vazio, sem ninguém perceber.

### Por que o pool de conexões é desativado

A configuração usa `NullPool`. Em ambiente serverless, os processos são
efêmeros e um pool manteria conexões ociosas que o Supabase acabaria
derrubando. Cada requisição abre e fecha a própria conexão, através do
Transaction pooler.

### Por que o controle de acesso está no código

O Supabase tem Row Level Security habilitado, mas a aplicação conecta com
usuário PostgreSQL, que passa por cima das políticas. O controle fica no
código, pelo método `acessivel_por()` dos modelos e por filtros nas consultas.
A vantagem é ter a regra em um lugar só, legível e testável; a contrapartida é
que um acesso direto ao banco não seria barrado pelo RLS.

### Por que existe a função `hoje()`

O servidor roda em UTC. Depois das 21h no horário de Brasília, `date.today()`
já devolveria o dia seguinte, e a agenda abriria no dia errado. A função
`hoje()` converte para `America/Sao_Paulo` e é usada em toda decisão de data.

### Por que a saída do grupo não apaga o registro

Registrar a saída preenche `data_saida` e mantém a linha. A lista de presença
histórica depende dessas linhas: apagar quem saiu deixaria presenças órfãs. Se
o paciente voltar, entra uma linha nova, e o histórico fica completo.

### Por que sessão de grupo não tem paciente

A tabela de agendamentos tem uma restrição que exige `paciente_id` **ou**
`grupo_id`, nunca os dois. A sessão de grupo é um único agendamento com
`tipo = 'GRUPO'`, e a presença de cada participante fica na tabela `presencas`.

## Segurança

| Risco | Tratamento |
| --- | --- |
| Senha exposta | Hash com `werkzeug.security`; o hash nunca é serializado nas respostas JSON |
| Sessão forjada | Cookie assinado com `SESSION_SECRET`, `HttpOnly` e `SameSite=Lax` |
| CSRF | Token obrigatório em todo formulário POST |
| Acesso indevido a prontuário | `acessivel_por()` nos modelos e filtros por perfil nas consultas |
| Segredo versionado | `.env` no `.gitignore`; variáveis ficam na plataforma |
| SQL injection | Consultas via SQLAlchemy, sempre parametrizadas |

## Testes

Os 144 testes rodam em SQLite na memória, criado e destruído a cada teste. Isso
os torna rápidos e independentes do Supabase, mas cria uma diferença conhecida:
as restrições `CHECK` e as chaves estrangeiras do PostgreSQL não são todas
reproduzidas. Por isso as regras críticas são validadas também no código da
aplicação, e não apenas no banco.