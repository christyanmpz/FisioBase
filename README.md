# FisioBase

Sistema web de gestão para o setor de fisioterapia de um consultório,
desenvolvido como Projeto Integrador.

O sistema substitui o controle manual em fichas de papel e planilhas Excel:
triagem, cadastro de pacientes, agenda de avaliações e sessões, prontuário
eletrônico, grupos terapêuticos, alta com histórico e relatórios mensais de
presença.

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
| `ADMIN` | Toda a clínica: todos os pacientes, agendas, ciclos, grupos e relatórios. Só o admin cadastra e desativa profissionais e mantém os feriados. |
| `FISIOTERAPEUTA` | Apenas os próprios pacientes, ciclos, agendamentos e os grupos que conduz. |

O escopo é aplicado pelo método `acessivel_por()` dos modelos e por filtros nas
consultas. Acesso indevido devolve 403.

### Fluxo de trabalho

**1. Triagem.** Menu *Triagem*. A agenda mostra os horários fixos de avaliação
de cada profissional e quais estão ocupados. Escolha um horário livre e o
paciente. Fora da urgência, a avaliação é marcada em um desses horários.

Fratura, AVC, pré e pós-operatório entram como **urgência**: encaixe fora da
grade, com o motivo obrigatório e registrado.

**2. Comparecimento à avaliação.** Duas saídas possíveis:

- O paciente precisa de tratamento → abre-se o ciclo (passo 3).
- O paciente sai orientado → **alta direto na avaliação**, e nenhum ciclo é
  aberto.

**3. Cadastro do paciente.** Menu *Pacientes → Novo paciente*. Nome, CPF,
cartão cidadão, nascimento e contato. O CPF é validado pelos dígitos
verificadores e não aceita duplicidade. Cada paciente fica vinculado a um
fisioterapeuta responsável.

A busca aceita nome, CPF ou data de nascimento — que é como a recepção costuma
achar quem não lembra o CPF.

**4. Ciclo de tratamento.** Na ficha do paciente, *Gerenciar ciclos → Novo
ciclo*. O ciclo define a região tratada (ombro, joelho, coluna ou outro), a
modalidade, o CID, o diagnóstico e o total de sessões, normalmente 10.

O ciclo **só pode ser aberto depois de o paciente comparecer a uma avaliação**.
Um paciente pode ter mais de um ciclo ativo ao mesmo tempo.

**5. Agendar.** Menu *Agenda → Novo agendamento*, ou o botão *Gerar sessões* no
ciclo, que cria todas as datas de uma vez a partir do dia da primeira sessão,
do horário e dos dias da semana. A geração pula fim de semana e feriado, avisa
quais datas foram puladas e leva ao *Cartão* para impressão.

Se o tratamento precisar mudar de dia ou horário, *Remarcar* move as sessões
futuras de uma vez. O que já aconteceu não é tocado.

**6. Presença.** Na agenda do dia, altere a situação:

| Situação | O que significa |
| --- | --- |
| Compareceu | Conta como atendimento realizado |
| Falta justificada | Avisou com antecedência. Pede o motivo, **conta como atendimento realizado** e gera reposição |
| Faltou | Não avisou. Entra na coluna de faltas e não gera reposição |
| Cancelado | Desmarcado pelo setor. Gera reposição |

O **comparecimento** só é aceito a partir do dia da sessão. A **ausência pode
ser lançada antes**, porque o paciente avisa com antecedência.

**7. Evolução.** Na ficha do paciente, a coluna *Evolução* de cada sessão:

| Link | Quando aparece |
| --- | --- |
| Registrar | Sessão sua, sem evolução ainda |
| Editar | Evolução existente que você pode alterar |
| Ver | Evolução de outro profissional, em somente leitura |
| — | Sessão com falta, cancelada ou futura |

Salvar a evolução de uma sessão ainda agendada muda a situação para *Compareceu*
automaticamente.

**8. Encerrar.** O ciclo é encerrado com motivo: alta, conclusão ou abandono.

**9. Alta do paciente.** Na ficha, *Dar alta* com o motivo. O sistema encerra os
ciclos ativos, cancela as sessões futuras e marca o paciente como fora de
acompanhamento. **Nada é apagado.** Se o paciente voltar, *Reativar paciente*
devolve o cadastro com todo o histórico — não cadastre de novo, porque isso
partiria a história em duas fichas.

### Grupos terapêuticos

Menu *Grupos*. Cada grupo tem dia e horário fixos na semana, região,
capacidade — 14 pessoas por padrão — e o número de semanas do ciclo.

O encontro dura 1 hora e ocupa dois horários seguidos da grade, então nem todo
horário pode iniciar um grupo.

**Gerar os encontros.** O botão *Sessões* cria um encontro por semana a partir
da data do primeiro, pulando feriado. Cada encontro vale por duas sessões
individuais.

**Compor.** O botão *Pacientes* abre a composição. Ao inscrever alguém, o
sistema o coloca em cada encontro já marcado, o que faz as datas aparecerem no
cartão dele. A saída não apaga o registro: preenche a data e o motivo e mantém
o histórico, que a lista de presença precisa.

**Chamada.** O botão *Presença* abre a lista com os inscritos nas linhas e as
datas nas colunas. **No grupo não há reposição** — a data é da turma inteira.

**Evolução.** Uma evolução por encontro, escrita uma vez para a turma, porque a
conduta é a mesma para todos. O que varia por pessoa é a presença.

Na agenda, o bloco do grupo segura o horário mas não é atendimento de ninguém:
a linha leva à lista de presença, e quem conta nos números é a presença de cada
inscrito.

Grupos não são excluídos, apenas desativados.

### Impressões

| Documento | Onde |
| --- | --- |
| Grade semanal do profissional | Agenda → *Grade semanal* |
| Grade do dia do setor | Agenda → *Grade do dia* |
| Cartão com as datas do paciente | Ciclo → *Cartão* |
| Prontuário completo | Ficha do paciente → *Imprimir prontuário* |
| Resumo do grupo | Grupo → *Resumo* |
| Resumo de atendimentos | Relatórios → *Imprimir resumo* |

A folha de evolução de uma sessão também sai pela tela da própria evolução.

O cartão de um ciclo de grupo sai identificado como tal, com o nome da turma, o
encontro semanal e o aviso de que não há reposição individual.

### Feriados

Menu *Configuração → Feriados*, só para o administrador.

Os **feriados nacionais** são importados da [BrasilAPI](https://brasilapi.com.br),
um serviço público e gratuito, sem cadastro nem chave. Escolha o ano e clique em
*Importar*. Repetir o mesmo ano é seguro: o que já existe não é duplicado.

**Ponto facultativo, feriado municipal e emenda** não vêm da API, porque variam
por cidade e por decisão da secretaria. Esses são cadastrados à mão, com data,
nome e tipo. Quando o dia já tem atendimento marcado, o sistema avisa quantos
são — cadastrar o feriado **não desmarca ninguém**.

Para uma emenda, remova a data antiga e cadastre a nova.

> **Importe também o ano seguinte.** A geração de sessões procura feriados numa
> janela de 400 dias à frente, então um ciclo aberto hoje já alcança o ano que
> vem.

Se a BrasilAPI estiver fora do ar, a tela avisa e o sistema segue com os
feriados já cadastrados.

### Relatórios

Menu *Relatórios*. Filtro por semana, mês ou ano.

O **resumo numérico** traz realizados, faltas e o total no ano, separando sessão
de avaliação — é a mesma conta que a clínica soma à mão na planilha. Abaixo, os
gráficos: atendimentos por horário, queixas por região, situação dos
agendamentos e, só para o admin, atendimentos por profissional.

O fisioterapeuta vê somente os próprios números.

## Stack

- **Backend:** Python 3.12 + Flask, com a fábrica `create_app`
- **Banco:** PostgreSQL no Supabase; SQLite em memória nos testes
- **ORM:** Flask-SQLAlchemy
- **Autenticação:** Flask-Login, hash com `werkzeug.security`
- **Proteção CSRF:** Flask-WTF
- **Front:** Jinja + HTML, CSS e JavaScript próprios; Chart.js nos relatórios
- **Integração:** BrasilAPI, consultada com `urllib` da biblioteca padrão
- **Testes:** pytest
- **Formatação:** Black
- **Deploy:** Vercel, automático a cada push na `main`

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

São **461 testes** em 35 arquivos, que rodam em SQLite na memória. Não abrem
conexão com o Supabase e não tocam em dado real. A chamada à BrasilAPI é
substituída por uma resposta simulada.

| Arquivo | O que cobre | Testes |
| --- | --- | ---: |
| `test_auth.py` | Login, logout, usuário desativado | 11 |
| `test_api.py` | Rotas JSON | 8 |
| `test_pacientes.py` | Cadastro, CPF, escopo por perfil | 11 |
| `test_busca_paciente.py` | Busca por nome, CPF e nascimento | 9 |
| `test_cartao_cidadao.py` | Cartão cidadão no cadastro | 8 |
| `test_paginacao.py` | Paginação e sugestões | 9 |
| `test_ciclos.py` | Abertura e encerramento do ciclo | 8 |
| `test_ciclo_edicao.py` | Edição e remarcação | 13 |
| `test_historico_por_ciclo.py` | Histórico separado por ciclo | 6 |
| `test_agenda.py` | Agendamento e validações | 12 |
| `test_agenda_filtros.py` | Filtros da agenda | 9 |
| `test_expediente.py` | Grade, dias úteis e limite por horário | 15 |
| `test_falta_justificada.py` | Motivo e efeito nos números | 11 |
| `test_reposicao.py` | Reposição automática ao fim do ciclo | 13 |
| `test_evolucao.py` | Registro da evolução | 9 |
| `test_evolucao_regras.py` | Quem pode editar e quando | 15 |
| `test_triagem.py` | Horários fixos, urgência e alta na avaliação | 19 |
| `test_alta_paciente.py` | Alta, reativação e ciclo após avaliação | 18 |
| `test_grupos.py` | Cadastro e regras do grupo | 28 |
| `test_grupos_composicao.py` | Entrada e saída de participantes | 21 |
| `test_grupo_sessoes.py` | Encontros, inscrição e presença | 19 |
| `test_grupo_gestao.py` | Evolução, saída e resumo do grupo | 19 |
| `test_cartao.py` | Cartão do paciente e feriados nas datas | 18 |
| `test_cartao_de_grupo.py` | Cartão de grupo × individual | 4 |
| `test_feriados.py` | Importação da BrasilAPI e cadastro à mão | 27 |
| `test_dashboards.py` | Painéis por perfil | 9 |
| `test_grades.py` | Grade semanal e do dia | 12 |
| `test_impressao.py` | Prontuário e folha de evolução | 10 |
| `test_folhas_impressas.py` | Cabeçalho e rodapé das folhas | 3 |
| `test_relatorio_resumo.py` | Resumo numérico do período | 9 |
| `test_rotulos_de_status.py` | Nome de cada situação nas telas | 13 |
| `test_visual_situacoes.py` | Uma cor por situação | 17 |
| `test_contraste_e_avisos.py` | Contraste do texto e aviso flutuante | 22 |
| `test_documentacao.py` | Rotas, tabelas e contagens desta documentação | 19 |
| `test_conexao.py` | Driver do banco na string de conexão | 7 |

## Banco de dados

O esquema foi criado uma vez, manualmente, pelo SQL Editor do Supabase. A
aplicação não executa `db.create_all()` nem migrações automáticas: em ambiente
serverless isso rodaria a cada cold start. As alterações posteriores estão
versionadas em `sql/`, uma por etapa.

Tabelas: `usuarios`, `pacientes`, `ciclos_tratamento`, `grupos`,
`grupo_pacientes`, `agendamentos`, `evolucoes`, `evolucoes_grupo`,
`horarios_triagem`, `feriados`, `cartoes` e `presencas`, mais a view
`vw_relatorio_mensal`.

A tabela `presencas` **não é usada**: a presença no grupo é um agendamento, com
`grupo_id` e `paciente_id` preenchidos. O motivo está em
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

O diagrama e a descrição de cada tabela estão em
[`docs/BANCO_DE_DADOS.md`](docs/BANCO_DE_DADOS.md).

Row Level Security está habilitado, mas a aplicação conecta com usuário
PostgreSQL, que passa por cima dele. O controle de acesso é feito no código.

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
São 16 horários por dia; as 12:00 ficam fora da grade, para o almoço.
Atendimento de segunda a sexta.

**Limite por horário.** No máximo 2 pacientes por profissional no mesmo
horário. Profissionais diferentes não conflitam, e agendamento cancelado libera
a vaga.

**Numeração de sessão.** Conta apenas os atendimentos realizados. É assim que a
reposição funciona: se o paciente falta, a sessão não é consumida. O sistema
recusa agendar além do total de sessões do ciclo.

**Comparecimento e ausência.** O comparecimento só é registrado a partir do dia
da sessão. A ausência pode ser lançada antes, porque o paciente avisa com
antecedência.

**O que conta como atendimento.** Comparecimento e falta justificada contam
como realizado. Só a falta não avisada entra na coluna de faltas. Falta
justificada e cancelamento pelo setor geram uma sessão de reposição ao fim do
ciclo.

**Ciclo depois da avaliação.** O ciclo só é aberto quando o paciente já
compareceu a uma avaliação. E pode não haver ciclo nenhum, se ele sair
orientado e com alta.

**Evolução clínica.** Pode ser editada depois. Podem editar o autor, o
fisioterapeuta responsável pela sessão e o admin. Quem tem acesso ao paciente
mas não à sessão vê em somente leitura.

**Grupos.** Encontro semanal de 1 hora, equivalente a duas sessões individuais.
Capacidade de 1 a 20 pessoas, 14 por padrão, organizadas por região. O mesmo
profissional não pode conduzir dois grupos em horários que se sobreponham. No
grupo não há reposição.

**Alta.** Encerra os ciclos ativos e cancela as sessões futuras, preservando
todo o histórico. A reativação devolve o paciente ao acompanhamento com esse
histórico.

**Fuso horário.** O servidor da Vercel roda em UTC. Todas as decisões de data
usam a função `hoje()`, que converte para `America/Sao_Paulo`. Sem isso, depois
das 21h a agenda abriria no dia seguinte.

## Rotas

São 53 endereços, alguns atendendo GET e POST. Todos exigem sessão, exceto o
login.

### Acesso

| Rota | Método | Descrição |
| --- | --- | --- |
| `/login` | GET, POST | Formulário e autenticação |
| `/logout` | POST | Encerra a sessão |
| `/` | GET | Redireciona ao painel do perfil |
| `/dashboard/admin` | GET | Painel do administrador |
| `/dashboard/fisioterapeuta` | GET | Painel do fisioterapeuta |

### Pacientes

| Rota | Método | Descrição |
| --- | --- | --- |
| `/pacientes` | GET | Lista, com busca por nome, CPF ou nascimento |
| `/pacientes/novo` | GET, POST | Cadastro |
| `/pacientes/<id>` | GET | Ficha com histórico por ciclo |
| `/pacientes/<id>/editar` | GET, POST | Edição |
| `/pacientes/<id>/alta` | POST | Alta com motivo |
| `/pacientes/<id>/reativar` | POST | Volta ao acompanhamento |
| `/pacientes/<id>/prontuario` | GET | Folha de impressão |

### Ciclos

| Rota | Método | Descrição |
| --- | --- | --- |
| `/pacientes/<id>/ciclos` | GET | Ciclos do paciente |
| `/pacientes/<id>/ciclos/novo` | GET, POST | Abertura do ciclo |
| `/ciclos/<id>/editar` | GET, POST | Edição do ciclo |
| `/ciclos/<id>/sessoes` | GET, POST | Geração das datas |
| `/ciclos/<id>/remarcar` | GET, POST | Remarca as sessões futuras |
| `/ciclos/<id>/encerrar` | POST | Encerramento com motivo |
| `/ciclos/<id>/responsavel` | POST | Troca de responsável (admin) |
| `/ciclos/<id>/cartao` | GET | Cartão para impressão |

### Agenda

| Rota | Método | Descrição |
| --- | --- | --- |
| `/agenda` | GET | Atendimentos do dia |
| `/agenda/semana` | GET | Grade semanal do profissional |
| `/agenda/dia` | GET | Grade do dia do setor |
| `/agenda/novo` | GET, POST | Novo agendamento |
| `/agendamentos/<id>/status` | POST | Altera a situação |
| `/agendamentos/<id>/evolucao` | GET, POST | Evolução clínica |

### Triagem

| Rota | Método | Descrição |
| --- | --- | --- |
| `/triagem` | GET | Agenda de avaliações |
| `/triagem/agendar` | GET, POST | Marca a avaliação |
| `/triagem/<id>/alta` | POST | Alta direto na avaliação |
| `/triagem/horarios` | GET, POST | Horários fixos de triagem |
| `/triagem/horarios/<id>/remover` | POST | Remove um horário |

### Grupos

| Rota | Método | Descrição |
| --- | --- | --- |
| `/grupos` | GET | Lista de grupos |
| `/grupos/novo` | GET, POST | Cadastro |
| `/grupos/<id>/editar` | GET, POST | Edição |
| `/grupos/<id>/situacao` | POST | Ativa ou desativa |
| `/grupos/<id>/sessoes` | GET, POST | Gera os encontros |
| `/grupos/<id>/pacientes` | GET, POST | Composição |
| `/grupos/<id>/pacientes/<id>/saida` | POST | Saída com motivo |
| `/grupos/<id>/presenca` | GET | Lista de presença |
| `/grupos/<id>/presenca/<id>` | POST | Marca a presença |
| `/grupos/<id>/encontros/<id>/evolucao` | GET, POST | Evolução do encontro |
| `/grupos/<id>/resumo` | GET | Resumo para impressão |

### Configuração

| Rota | Método | Descrição |
| --- | --- | --- |
| `/relatorios` | GET | Resumo numérico e gráficos |
| `/usuarios` | GET | Lista de profissionais (admin) |
| `/usuarios/novo` | GET, POST | Cadastro (admin) |
| `/usuarios/<id>/desativar` | POST | Desativação (admin) |
| `/feriados` | GET | Feriados cadastrados (admin) |
| `/feriados` | POST | Cadastro à mão (admin) |
| `/feriados/importar` | POST | Importa da BrasilAPI (admin) |
| `/feriados/<id>/remover` | POST | Remove um feriado (admin) |

### JSON

`POST /api/auth/login`, `GET /api/auth/session`, `POST /api/auth/logout` e
`GET /api/admin/users`. Ver as [pendências conhecidas](#pendências-conhecidas).

## Estrutura de arquivos

```
FisioBase/
├── app.py                 # fábrica create_app e todas as rotas
├── models.py              # modelos SQLAlchemy
├── integracoes.py         # chamadas a serviços de fora
├── index.py               # entrypoint da Vercel
├── vercel.json            # configuração de build
├── requirements.txt
├── pytest.ini
├── docs/                  # documentação do Projeto Integrador
├── sql/                   # alterações de esquema, uma por etapa
├── templates/             # 34 templates Jinja
├── static/
│   ├── css/style.css
│   └── js/app.js
└── tests/                 # 461 testes em 35 arquivos
```

## Documentação do projeto

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — camadas, decisões técnicas e segurança
- [`docs/BANCO_DE_DADOS.md`](docs/BANCO_DE_DADOS.md) — diagrama e descrição das tabelas
- [`docs/CASOS_DE_USO.md`](docs/CASOS_DE_USO.md) — atores, fluxos e matriz de permissões
- [`docs/REQUISITOS.md`](docs/REQUISITOS.md) — requisitos, regras de negócio e rastreabilidade

## Pendências conhecidas

**As rotas `/api/auth/*` são isentas de CSRF e não aplicam o bloqueio por
tentativas.** Os campos `falhas_login` e `bloqueado_ate` existem na tabela de
usuários, mas essas rotas não os consultam, ao contrário do formulário de login
normal. Como o repositório é público e o sistema está no ar, é um caminho
aberto para tentativa de senha por força bruta.

Essas rotas foram criadas para um front React que não faz parte do sistema
entregue: nenhum template ou JavaScript do FisioBase as chama. A correção é
removê-las ou submetê-las às mesmas regras do formulário. As pastas
`lib/api-zod/`, `lib/api-client-react/` e `scripts/src/` são restos desse mesmo
front.

**Não há troca de senha** pelo próprio usuário nem redefinição pelo admin.

**A tabela `presencas` está no banco e não é usada.** Não foi removida porque
apagar tabela em produção é irreversível.

**O encontro de grupo não bloqueia o horário do profissional** para atendimento
individual: a verificação de conflito só compara grupo com grupo. Falta
confirmar com a clínica se isso é intencional — sala separada, outro
profissional cobrindo — ou se o horário do grupo deveria travar a agenda dele.

**Trabalho futuro mapeado com a clínica**, e conscientemente fora desta entrega:

- Consulta pública das próprias datas por link, sem login. Expor dado de
  paciente em link aberto é risco de LGPD e precisa de decisão da clínica.
- Integração com Google Agenda e lembrete por e-mail. Depende de conta
  institucional e de política sobre mensagem automática a paciente.
