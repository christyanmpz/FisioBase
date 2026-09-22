# Banco de dados

PostgreSQL gerenciado pelo Supabase. O esquema foi criado uma vez pelo SQL
Editor e é alterado manualmente; a aplicação não executa migrações.

## Diagrama de entidades

```
                         ┌──────────────┐
                         │   usuarios   │
                         │──────────────│
                         │ id (PK)      │
                         │ nome         │
                         │ email (uniq) │
                         │ senha_hash   │
                         │ perfil       │
                         │ ativo        │
                         └──────┬───────┘
                                │ responsável
            ┌───────────────────┼────────────────────┬──────────────┐
            │                   │                    │              │
            ▼                   ▼                    ▼              ▼
     ┌─────────────┐   ┌──────────────────┐   ┌────────────┐  ┌──────────┐
     │  pacientes  │   │ ciclos_tratamento│   │  grupos    │  │evolucoes │
     │─────────────│   │──────────────────│   │────────────│  │──────────│
     │ id (PK)     │◄──┤ paciente_id (FK) │   │ id (PK)    │  │ id (PK)  │
     │ nome        │   │ fisioterapeuta_id│   │ nome       │  │ ciclo_id │
     │ cpf (uniq)  │   │ regiao           │   │ regiao     │  │paciente_id│
     │ data_nasc.  │   │ modalidade       │   │dia_semana  │  │agendam_id│
     │ telefone    │   │ data_avaliacao   │   │ hora       │  │ data     │
     │ cid         │   │ total_sessoes    │   │capac_max   │  │descricao │
     │ diagnostico │   │ status           │   │ ativo      │  │evolucao  │
     │ ativo       │   │ data_alta        │   └─────┬──────┘  └────┬─────┘
     │fisiot_id(FK)│   └────────┬─────────┘         │              │
     └──────┬──────┘            │                   │              │
            │                   │                   │              │
            │         ┌─────────┴───────────────────┴───┐          │
            │         │        agendamentos             │◄─────────┘
            │         │─────────────────────────────────│
            │         │ id (PK)                         │
            └────────►│ paciente_id (FK, nulo em grupo) │
                      │ grupo_id (FK, nulo se individual)│
                      │ ciclo_id (FK)                   │
                      │ fisioterapeuta_id (FK)          │
                      │ tipo, data, hora, duracao_min   │
                      │ numero_sessao, status           │
                      └────────────────┬────────────────┘
                                       │
                      ┌────────────────┴────────┐
                      │       presencas         │
                      │─────────────────────────│
                      │ id (PK)                 │
                      │ agendamento_id (FK)     │
                      │ paciente_id (FK)        │
                      │ status, justificativa   │
                      └─────────────────────────┘

     ┌────────────────────┐        ┌──────────┐      ┌──────────┐
     │  grupo_pacientes   │        │ feriados │      │ cartoes  │
     │────────────────────│        │──────────│      │──────────│
     │ id (PK)            │        │ id (PK)  │      │ id (PK)  │
     │ grupo_id (FK)      │        │ data     │      │ciclo_id  │
     │ paciente_id (FK)   │        │ nome     │      │gerado_por│
     │ ciclo_id (FK)      │        │ tipo     │      │gerado_em │
     │ data_entrada       │        └──────────┘      └──────────┘
     │ data_saida (nulo = │
     │  participação ativa)│
     └────────────────────┘
```

## Dicionário de dados

### usuarios

Profissionais com acesso ao sistema.

| Coluna | Tipo | Observação |
| --- | --- | --- |
| `id` | serial | Chave primária |
| `nome` | varchar(120) | |
| `email` | varchar(120) | Único; usado no login |
| `senha_hash` | varchar(255) | Hash gerado por `werkzeug.security` |
| `perfil` | varchar(30) | `ADMIN` ou `FISIOTERAPEUTA` |
| `ativo` | boolean | Usuário inativo não consegue entrar |
| `falhas_login` | integer | Reservado para bloqueio por tentativas |
| `bloqueado_ate` | timestamptz | Reservado para bloqueio por tentativas |

### pacientes

| Coluna | Tipo | Observação |
| --- | --- | --- |
| `id` | serial | Chave primária |
| `nome` | varchar(150) | |
| `cpf` | varchar(14) | Único; validado pelos dígitos verificadores |
| `data_nascimento` | date | |
| `telefone`, `email`, `endereco` | varchar | Contato |
| `cartao_cidadao` | varchar(15) | Identificação do município; 10 a 15 dígitos |
| `observacoes` | text | |
| `ativo` | boolean | Se está em acompanhamento hoje; sair é alta, não exclusão |
| `data_alta` | date | Quando saiu da última vez |
| `motivo_alta` | text | Por que saiu; consultado no histórico e na reativação |
| `cid`, `diagnostico` | varchar(30), text | Legado. Migrados para `ciclos_tratamento` na etapa 3; ficam no banco como histórico e não são mais escritos |
| `fisioterapeuta_id` | integer | Profissional responsável |

### ciclos_tratamento

Amarra a avaliação às sessões. Um paciente pode ter vários ciclos ativos ao
mesmo tempo, por exemplo joelho e coluna.

| Coluna | Tipo | Observação |
| --- | --- | --- |
| `paciente_id` | integer | |
| `fisioterapeuta_id` | integer | Herdado do paciente, mas editável pelo admin |
| `regiao` | varchar(30) | Ombro, joelho, coluna ou outro; é o que liga o paciente ao grupo |
| `cid` | varchar(30) | Código do diagnóstico que justifica este ciclo |
| `diagnostico` | text | Justificativa clínica, como veio do médico |
| `modalidade` | varchar(20) | `INDIVIDUAL` ou `GRUPO` |
| `data_avaliacao` | date | |
| `total_sessoes` | integer | Normalmente 10 |
| `status` | varchar(20) | `ATIVO`, `CONCLUIDO`, `ALTA` ou `ABANDONO` |
| `data_alta` | date | Preenchida no encerramento |

### agendamentos

| Coluna | Tipo | Observação |
| --- | --- | --- |
| `tipo` | varchar(20) | `AVALIACAO`, `SESSAO` ou `GRUPO` |
| `paciente_id` | integer | Nulo em sessão de grupo |
| `grupo_id` | integer | Nulo em atendimento individual |
| `ciclo_id` | integer | |
| `fisioterapeuta_id` | integer | Obrigatório |
| `data`, `hora` | date, time | |
| `duracao_min` | integer | 30 individual, 60 em grupo |
| `numero_sessao` | integer | Conta apenas sessões realizadas |
| `status` | varchar(20) | `AGENDADO`, `CONFIRMADO`, `REALIZADO`, `CANCELADO`, `FALTOU` ou `FALTA_JUSTIFICADA` |

A falta justificada guarda o motivo no campo `observacoes` do próprio
agendamento, em vez de uma coluna nova.

**Restrição `chk_ag_alvo`:** desde a etapa 4A o agendamento assume três
formas, e a restrição cobre exatamente essas três:

| `tipo` | `grupo_id` | `paciente_id` | O que é |
| --- | --- | --- | --- |
| `GRUPO` | sim | não | O encontro do grupo, que ocupa a grade uma vez |
| `SESSAO` | opcional | sim | Atendimento individual, ou presença no grupo |
| `AVALIACAO` | não | sim | Triagem |

A presença de cada inscrito num encontro é um agendamento de tipo `SESSAO`
com `grupo_id` preenchido. É isso que faz a participação em grupo aparecer no
histórico do paciente, no cartão e nos relatórios sem código duplicado. Nas
telas de agenda essas linhas são escondidas — quem aparece lá é o encontro.

### grupos e grupo_pacientes

| Coluna | Observação |
| --- | --- |
| `grupos.dia_semana` | 0 a 6, convenção do Python: 0 é segunda |
| `grupos.hora` | Início do encontro semanal, de 1 hora |
| `grupos.capacidade_max` | Padrão 14; o banco aceita de 1 a 20 |
| `grupos.total_semanas` | Duração do tratamento; padrão 6, que valem 12 sessões |
| `grupo_pacientes.data_entrada` | Data em que o paciente entrou |
| `grupo_pacientes.data_saida` | Nula enquanto a participação está ativa |
| `grupo_pacientes.motivo_saida` | Por que saiu antes do fim; vai para a alta |

A convenção de `dia_semana` merece atenção: o PostgreSQL usa 0 para domingo na
função `extract(dow ...)`, enquanto aqui 0 é segunda. Uma consulta em SQL que
compare as duas precisa converter.

### evolucoes

Registro clínico de cada sessão individual. O `paciente_id` é obrigatório,
então a evolução coletiva de grupo vive em `evolucoes_grupo`.

### evolucoes_grupo

Uma anotação por encontro do grupo: no grupo os exercícios são os mesmos para
todos os inscritos, e o que muda por pessoa é só a presença. A restrição
`uq_evo_grupo_data` garante uma linha por data — salvar de novo corrige, não
duplica.

### presencas

**Tabela morta.** Veio do esquema original, nunca foi usada pela aplicação e
não tem modelo em `models.py`. A chamada do grupo é feita em `agendamentos`,
como descrito acima, para reaproveitar histórico, cartão e relatórios. Pode
ser removida quando houver certeza de que está vazia.

### horarios_triagem

Os horários que cada profissional reserva na semana para o primeiro contato
com o paciente — na planilha da clínica, as células marcadas com "T =". A
avaliação é agendada neles; urgências (fratura, AVC, pré e pós-operatório)
entram fora da grade, com o motivo registrado na observação do agendamento.
`uq_triagem_slot` impede o mesmo horário duas vezes para o mesmo
profissional, e remover desativa em vez de apagar.

### feriados

Datas que a geração automática pula. O campo `tipo` distingue `NACIONAL`,
`MUNICIPAL` e `FACULTATIVO`. Os nacionais de 2026 e 2027 são carregados por
script; os demais são inseridos manualmente, porque variam por cidade.

### cartoes

Registra a emissão do cartão de um ciclo: quem gerou e quando. O cartão em si é
montado na hora, a partir dos agendamentos, então ele sempre reflete a agenda
atual mesmo que uma sessão seja remarcada.

## Integridade

- Chaves estrangeiras em todos os relacionamentos.
- `grupo_pacientes` é apagado em cascata se o grupo for excluído. Na prática a
  aplicação nunca exclui grupos, apenas desativa.
- Restrições `CHECK` garantem os valores de `perfil`, `status`, `tipo`,
  `regiao`, `dia_semana` e `capacidade_max`.
- Row Level Security habilitado, mas a aplicação conecta com usuário
  PostgreSQL, que passa por cima dele.