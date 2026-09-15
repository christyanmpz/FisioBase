# FisioBase

Sistema web de gestão para o setor de fisioterapia de um consultório,
desenvolvido como Projeto Integrador.

O sistema substitui o controle manual em fichas de papel e planilhas Excel:
cadastro de pacientes, agenda de avaliações e sessões, prontuário eletrônico,
grupos terapêuticos e relatórios mensais de presença.

- **Aplicação em produção:** https://fisiobase.vercel.app
- **Repositório:** https://github.com/christyanmpz/FisioBase

## Sumário

- [Como usar](#como-usar)
- [Stack](#stack)
- [Instalação](#instalação)
- [Testes](#testes)
- [Banco de dados](#banco-de-dados)
- [Regras de negócio](#regras-de-negócio)
- [Rotas](#rotas)
- [Estrutura de arquivos](#estrutura-de-arquivos)
- [Documentação do projeto](#documentação-do-projeto)
- [Pendências conhecidas](#pendências-conhecidas)

## Como usar

### Perfis de acesso

| Perfil | O que enxerga |
| --- | --- |
| `ADMIN` | Toda a clínica: todos os pacientes, agendas, ciclos, grupos e relatórios. Só o admin cadastra e desativa profissionais. |
| `FISIOTERAPEUTA` | Apenas os próprios pacientes, ciclos, agendamentos e os grupos que conduz. |

O escopo é aplicado no código, pelo método `acessivel_por()` dos modelos e por
filtros nas consultas. Tentar abrir um registro de outro profissional devolve
403.

### Fluxo de trabalho

**1. Cadastrar o paciente.** Menu *Pacientes* → *Novo paciente*. O CPF é
validado pelos dígitos verificadores e não aceita duplicidade. O paciente fica
vinculado a um fisioterapeuta responsável.

**2. Abrir o ciclo de tratamento.** Na ficha do paciente, *Gerenciar ciclos* →
*Novo ciclo*. O ciclo amarra a avaliação às sessões e define a região tratada
(ombro, joelho, coluna ou outro) e o total de sessões, normalmente 10. Um
paciente pode ter mais de um ciclo ativo ao mesmo tempo, por exemplo joelho e
coluna.

**3. Agendar.** Menu *Agenda* → *Novo agendamento*. O sistema recusa horário
fora do expediente, fim de semana e data passada, e respeita o limite de 2
pacientes por profissional no mesmo horário.

**4. Registrar presença.** Na agenda, altere a situação do atendimento para
*Realizado*, *Faltou* ou *Cancelado* e clique em *Salvar*. Presença e falta só
são aceitas a partir do dia da sessão.

**5. Registrar a evolução clínica.** Na ficha do paciente, coluna *Evolução*, o
link muda conforme a situação:

| Link | Significado |
| --- | --- |
| **Registrar** | A sessão aceita evolução e ainda não tem uma |
| **Editar** | Já existe evolução e o usuário pode corrigi-la |
| **Ver** | O usuário tem acesso ao paciente, mas não pode editar |
| **—** | A sessão não aceita evolução (falta, cancelamento ou data futura) |

Ao salvar a evolução de uma sessão ainda agendada, ela passa automaticamente a
*Realizada*.

**6. Encerrar o ciclo.** Em *Gerenciar ciclos*, escolha o motivo do
encerramento: alta, conclusão ou abandono.

### Grupos terapêuticos

Menu *Grupos*. Cada grupo tem dia e horário fixos na semana, região e
capacidade, por padrão 14 pessoas. A sessão de grupo dura 1 hora e ocupa dois
horários seguidos da grade, então nem todo horário pode iniciar um grupo.

O botão *Pacientes* abre a composição, onde se adiciona e se registra a saída
de participantes. A saída não apaga o registro: preenche a data de saída e
mantém o histórico, que a lista de presença vai precisar.

Grupos não são excluídos, apenas desativados.

### Relatórios

Menu *Relatórios*, com filtro por mês e ano. Quatro gráficos: atendimentos por
horário, queixas por região, situação dos agendamentos e atendimentos por
profissional, este último apenas para o admin. O fisioterapeuta vê somente os
próprios números.

## Stack

- **Backend:** Python 3.12 + Flask, com fábrica `create_app`
- **Banco:** PostgreSQL no Supabase; SQLite em memória nos testes
- **ORM:** Flask-SQLAlchemy
- **Autenticação:** Flask-Login, senhas com hash `werkzeug.security`
- **Proteção CSRF:** Flask-WTF
- **Front:** templates Jinja com HTML, CSS e JavaScript próprios; Chart.js nos relatórios
- **Testes:** pytest
- **Formatação:** Black
- **Deploy:** Vercel, com publicação automática a cada push na `main`

## Instalação

```bash
git clone https://github.com/christyanmpz/FisioBase.git
cd FisioBase
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux e macOS
pip install -r requirements.txt
```

### Variáveis de ambiente

A aplicação **não sobe** sem estas duas variáveis. É intencional: evita que a
produção caia silenciosamente num banco local ou use uma chave de sessão
previsível.

| Variável | Descrição |
| --- | --- |
| `SUPABASE_DB_URL` | String de conexão PostgreSQL. Use o **Transaction pooler** do Supabase, porta 6543, com prefixo `postgresql://`. |
| `SESSION_SECRET` | Chave aleatória que assina o cookie de sessão. |

Em desenvolvimento, ficam num arquivo `.env` na raiz, que não é versionado. Em
produção, nas configurações de ambiente da Vercel.

A variável se chama `SUPABASE_DB_URL`, e não `DATABASE_URL`, porque alguns
ambientes de execução definem uma `DATABASE_URL` própria que sobrescreveria a
do Supabase.

### Executar

```bash
python app.py
```

A aplicação sobe em `http://localhost:5000`, ou na porta definida em `PORT`.

## Testes

```bash
python -m pytest -q
```

São **144 testes**, que rodam em SQLite na memória. Não abrem conexão com o
Supabase e não tocam em dado real.

| Arquivo | Testes | Cobre |
| --- | --- | --- |
| `test_auth.py` | 11 | Login, logout, bloqueio por perfil, usuário desativado |
| `test_api.py` | 8 | Endpoints JSON e não serialização do hash de senha |
| `test_pacientes.py` | 11 | CRUD, validação de CPF, busca, escopo de acesso |
| `test_ciclos.py` | 8 | Abertura, encerramento e troca de responsável |
| `test_agenda.py` | 12 | Agendamento, limite por horário, numeração de sessão |
| `test_expediente.py` | 13 | Grade de horários, dias úteis, recusa de data passada |
| `test_evolucao.py` | 9 | Registro, edição e autoria da evolução |
| `test_evolucao_regras.py` | 15 | Permissões, sessão futura, falta, fuso horário |
| `test_grupos.py` | 28 | CRUD de grupos, conflito de horário, escopo |
| `test_grupos_composicao.py` | 20 | Entrada, saída, capacidade, vínculo com ciclo |
| `test_dashboards.py` | 9 | Números e escopo dos painéis |

## Banco de dados

O esquema é criado **uma vez**, manualmente, pelo SQL Editor do Supabase. A
aplicação não executa `db.create_all()` nem migrações automáticas: em ambiente
serverless isso rodaria a cada cold start.

Tabelas: `usuarios`, `pacientes`, `ciclos_tratamento`, `grupos`,
`grupo_pacientes`, `agendamentos`, `presencas`, `evolucoes`, `feriados` e
`cartoes`, além da view `vw_relatorio_mensal`.

O diagrama e a descrição de cada tabela estão em
[`docs/BANCO_DE_DADOS.md`](docs/BANCO_DE_DADOS.md).

Row Level Security está habilitado, mas a aplicação conecta com usuário
PostgreSQL, que passa por cima dele. O controle de acesso ao dado clínico é
responsabilidade do código Flask.

### Primeiro usuário

Não há usuário padrão nem seed automático. Para criar o primeiro administrador,
gere o hash e insira no banco:

```python
from werkzeug.security import generate_password_hash
generate_password_hash("sua-senha")
```

```sql
INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo, falhas_login)
VALUES ('Nome', 'email@exemplo.com', 'hash-gerado-acima', 'ADMIN', TRUE, 0);
```

Os demais usuários são criados pela própria aplicação.

## Regras de negócio

**Expediente.** De 07:30 às 15:30, sessões de 30 minutos, encerrando às 16h.
São 16 horários por dia; o horário de almoço fica fora da grade. Atendimento de
segunda a sexta.

**Limite por horário.** No máximo 2 pacientes por profissional no mesmo
horário. Profissionais diferentes não conflitam, e agendamento cancelado libera
a vaga.

**Numeração de sessão.** Conta apenas os agendamentos com situação
*Realizado*. É assim que a reposição funciona: se o paciente falta, a sessão
não é consumida e a reposição recebe o mesmo número. O sistema recusa agendar
além do total de sessões do ciclo.

**Evolução clínica.** Registrada por sessão e editável depois. Podem editar o
autor, o fisioterapeuta responsável pela sessão e o admin. Quem tem acesso ao
paciente, mas não à sessão, vê em modo somente leitura, para que o profissional
substituto tenha contexto.

**Grupos.** Encontro semanal de 1 hora, equivalente a duas sessões individuais.
Capacidade de 12 a 14 pessoas, organizados por região. O mesmo profissional não
pode conduzir dois grupos em horários que se sobreponham.

**Fuso horário.** O servidor da Vercel roda em UTC. Todas as decisões de data
usam a função `hoje()`, que converte para `America/Sao_Paulo`. Sem isso, depois
das 21h a agenda abriria no dia seguinte.

## Rotas

| Método | Rota | Função |
| --- | --- | --- |
| GET/POST | `/login` | Autenticação |
| POST | `/logout` | Encerrar sessão |
| GET | `/dashboard/admin` | Painel do administrador |
| GET | `/dashboard/fisioterapeuta` | Painel do fisioterapeuta |
| GET | `/pacientes` | Lista, com busca por nome ou CPF |
| GET/POST | `/pacientes/novo` | Cadastro |
| GET | `/pacientes/<id>` | Ficha e histórico |
| GET/POST | `/pacientes/<id>/editar` | Edição |
| POST | `/pacientes/<id>/desativar` | Desativação |
| GET | `/pacientes/<id>/ciclos` | Ciclos do paciente |
| GET/POST | `/pacientes/<id>/ciclos/novo` | Abertura de ciclo |
| POST | `/ciclos/<id>/encerrar` | Encerramento |
| POST | `/ciclos/<id>/responsavel` | Troca de responsável (admin) |
| GET | `/agenda` | Agenda do dia |
| GET/POST | `/agenda/novo` | Novo agendamento |
| POST | `/agendamentos/<id>/status` | Presença, falta, cancelamento |
| GET/POST | `/agendamentos/<id>/evolucao` | Evolução clínica |
| GET | `/grupos` | Lista de grupos |
| GET/POST | `/grupos/novo` | Criação |
| GET/POST | `/grupos/<id>/editar` | Edição |
| POST | `/grupos/<id>/situacao` | Ativar ou desativar |
| GET | `/grupos/<id>/pacientes` | Composição |
| POST | `/grupos/<id>/pacientes` | Adicionar paciente |
| POST | `/grupos/<id>/pacientes/<id>/saida` | Registrar saída |
| GET | `/relatorios` | Relatório mensal |
| GET | `/usuarios` | Lista de profissionais (admin) |
| GET/POST | `/usuarios/novo` | Cadastro de profissional (admin) |
| POST | `/usuarios/<id>/desativar` | Desativação (admin) |

Endpoints JSON: `POST /api/auth/login`, `GET /api/auth/session`,
`POST /api/auth/logout` e `GET /api/admin/users`.

## Estrutura de arquivos

```
FisioBase/
├── app.py                 # fábrica create_app e todas as rotas
├── models.py              # modelos SQLAlchemy
├── index.py               # entrypoint da Vercel
├── vercel.json            # configuração de build
├── requirements.txt
├── pytest.ini
├── docs/                  # documentação do Projeto Integrador
├── templates/             # 20 templates Jinja
├── static/
│   ├── css/style.css
│   └── js/app.js
└── tests/                 # 144 testes
```

## Documentação do projeto

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — camadas, fluxo de uma requisição e decisões técnicas
- [`docs/BANCO_DE_DADOS.md`](docs/BANCO_DE_DADOS.md) — diagrama e dicionário de dados
- [`docs/CASOS_DE_USO.md`](docs/CASOS_DE_USO.md) — atores, casos de uso e fluxos
- [`docs/REQUISITOS.md`](docs/REQUISITOS.md) — requisitos funcionais e não funcionais

## Pendências conhecidas

- Os endpoints `/api/auth/login` e `/api/auth/logout` estão isentos de CSRF
  porque a interface React não envia o token. Os formulários HTML estão
  protegidos.
- Os campos `falhas_login` e `bloqueado_ate` existem na tabela de usuários, mas
  o bloqueio por tentativas ainda não é aplicado.
- Não há troca de senha pelo próprio usuário nem redefinição pelo admin.
- A lista de pacientes não tem paginação.
- Trabalho futuro mapeado com a clínica: disponibilidade do profissional
  (triagens fixas, reunião e horários fechados), geração automática das sessões
  com impressão do cartão, lista de presença dos grupos, grades semanal e diária
  para impressão, e registro de alta com histórico e reativação do cadastro.