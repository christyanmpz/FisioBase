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
    ├── Flask-SQLAlchemy .. acesso ao banco
    └── integracoes.py .... serviços de fora
    │                              │  HTTPS
    │                              └──────────► BrasilAPI (feriados nacionais)
    │  postgresql:// (Transaction pooler, porta 6543)
    ▼
Supabase (PostgreSQL)
```

O front é renderizado no servidor. O JavaScript no navegador cuida apenas de
detalhes de interface: mostrar ou ocultar a senha, controlar os avisos
flutuantes, revelar o campo de motivo quando a situação escolhida é falta
justificada, e transformar o seletor de paciente em uma caixa de busca com
sugestões. Nenhuma regra de negócio depende dele — sem JavaScript, o seletor
continua funcionando. Os gráficos usam Chart.js carregado por CDN.

## Camadas

| Camada | Arquivo | Responsabilidade |
| --- | --- | --- |
| Entrada | `index.py` | Expõe a aplicação para a Vercel |
| Configuração | `app.py` → `create_app()` | Lê variáveis de ambiente, inicializa extensões e registra rotas |
| Rotas e regras | `app.py` → `register_routes()` | Valida entrada, aplica regras de negócio e decide a resposta |
| Domínio | `models.py` | Modelos, relacionamentos e regras de acesso ao registro |
| Integrações | `integracoes.py` | Chamadas a serviços de fora, isoladas do resto |
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
do Supabase, e alterações são aplicadas manualmente, com o SQL versionado em
`sql/`.

A contrapartida é que o `models.py` pode divergir do banco sem ninguém notar,
porque os testes criam a tabela a partir do próprio `models.py`. Foi o que
aconteceu com a tabela `feriados`: o banco tinha `UNIQUE` na data e um `CHECK`
no tipo, e o modelo não tinha nenhum dos dois. Uma importação duplicada passava
no teste, em SQLite, e estouraria em produção. O modelo foi alinhado ao banco
quando isso apareceu.

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

### Por que a presença de grupo é um agendamento, e não uma tabela própria

O esquema original previa uma tabela `presencas` para a chamada do grupo. Ela
**não é usada**. A presença de cada inscrito é um registro em `agendamentos`,
com `grupo_id` e `paciente_id` preenchidos.

A razão é que tudo que a clínica precisa em volta da presença já existe para o
agendamento: histórico do paciente, cartão com as datas, contagem nos
relatórios e regra de quando a situação pode ser alterada. Uma tabela separada
obrigaria a duplicar cada uma dessas coisas.

O encontro do grupo em si é um agendamento com `tipo = 'GRUPO'` e sem paciente:
ele segura o horário na grade e não conta como atendimento de ninguém. Por isso
toda apuração de números filtra `tipo != 'GRUPO'`.

A tabela `presencas` continua no banco, vazia e sem uso. Não foi removida
porque apagar tabela em produção é irreversível e a decisão é da clínica.

### Por que a alta não apaga nada

Dar alta ao paciente encerra os ciclos ativos, cancela as sessões futuras e
marca o cadastro como fora de acompanhamento. O prontuário inteiro fica. Quando
o paciente volta — o que é comum —, a reativação devolve o cadastro com todo o
histórico, em vez de criar uma ficha nova que partiria a história em duas.

### Por que a integração fica isolada em `integracoes.py`

A busca dos feriados nacionais na BrasilAPI é a única chamada a um serviço de
fora. Ela vive em um módulo próprio, com três decisões deliberadas:

- **Usa `urllib`, da biblioteca padrão, e não `requests`.** O sistema roda em
  serverless, e cada dependência a mais é mais uma coisa que pode quebrar a
  publicação.
- **Tem prazo de espera de 8 segundos.** A tela não pode ficar pendurada
  esperando um serviço que não é nosso.
- **Os erros têm nome (`IntegracaoIndisponivel`) e a tela os trata.** A
  importação é uma ação manual do administrador: se a API estiver fora do ar, a
  tela avisa e o sistema segue com os feriados que já foram importados. Nenhuma
  tela do dia a dia depende dessa chamada.

Só o ano é enviado. Nenhum dado de paciente sai do sistema.

## Segurança

| Risco | Tratamento |
| --- | --- |
| Senha exposta | Hash com `werkzeug.security`; o hash nunca é serializado nas respostas JSON |
| Sessão forjada | Cookie assinado com `SESSION_SECRET`, `HttpOnly` e `SameSite=Lax` |
| CSRF | Token obrigatório em todo formulário POST |
| Acesso indevido a prontuário | `acessivel_por()` nos modelos e filtros por perfil nas consultas |
| Segredo versionado | `.env` no `.gitignore`; variáveis ficam na plataforma |
| SQL injection | Consultas via SQLAlchemy, sempre parametrizadas |
| Serviço externo fora do ar | Erro nomeado, prazo de espera e mensagem na tela; o sistema não para |

### Ponto fraco conhecido

As rotas `/api/auth/*` são isentas de CSRF e **não aplicam o bloqueio por
tentativas** que o formulário de login normal aplica. Os campos `falhas_login`
e `bloqueado_ate` existem na tabela de usuários, mas essas rotas não os
consultam. Como o repositório é público e o sistema está no ar, isso é um
caminho aberto para tentativa de senha por força bruta.

Essas rotas foram criadas para um front React que não faz parte do sistema
entregue: nenhum template ou JavaScript do FisioBase as chama. A correção é
removê-las ou submetê-las às mesmas regras do formulário.

## Testes

Os 461 testes rodam em SQLite na memória, criado e destruído a cada teste. Isso
os torna rápidos e independentes do Supabase, mas cria uma diferença conhecida:
as restrições `CHECK` e as chaves estrangeiras do PostgreSQL não são todas
reproduzidas. Por isso as regras críticas são validadas também no código da
aplicação, e não apenas no banco.

A chamada à BrasilAPI é substituída por uma resposta simulada nos testes. O que
se testa é o tratamento: formato esperado, serviço fora do ar, resposta que não
é JSON, erro HTTP e data malformada no meio da lista.

Parte dos testes verifica a interface e não só a regra: o contraste mínimo do
texto é calculado a partir do CSS publicado, e cada situação do atendimento é
renderizada de verdade para conferir se recebeu a cor certa.
