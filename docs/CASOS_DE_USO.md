# Casos de uso

## Atores

| Ator | Descrição |
| --- | --- |
| **Administrador** | Coordena o setor. Cadastra profissionais, enxerga todos os pacientes, agendas e relatórios, redireciona tratamentos entre profissionais e mantém os feriados. |
| **Fisioterapeuta** | Atende pacientes. Enxerga apenas os próprios pacientes, ciclos, agendamentos e os grupos que conduz. |

## Diagrama

```
                        ┌──────────────────────────────────────┐
                        │              FisioBase               │
                        │                                      │
                        │  ATENDIMENTO                         │
     ┌──────────┐       │  ┌────────────────────────────────┐  │
     │          │───────┼─►│ UC01 Autenticar                │  │
     │  Fisio-  │       │  │ UC02 Gerir pacientes           │  │
     │terapeuta │       │  │ UC03 Marcar avaliação          │  │
     │          │       │  │ UC04 Abrir ciclo               │  │
     └──────────┘       │  │ UC05 Agendar atendimento       │  │
                        │  │ UC06 Registrar presença        │  │
                        │  │ UC07 Registrar evolução        │  │
                        │  │ UC08 Editar e remarcar ciclo   │  │
                        │  │ UC09 Encerrar ciclo            │  │
                        │  │ UC10 Dar alta ao paciente      │  │
                        │  │ UC11 Reativar paciente         │  │
                        │  └────────────────────────────────┘  │
                        │                                      │
                        │  GRUPO                               │
                        │  ┌────────────────────────────────┐  │
                        │  │ UC12 Gerir grupos              │  │
                        │  │ UC13 Gerar encontros           │  │
                        │  │ UC14 Compor grupo              │  │
                        │  │ UC15 Marcar presença no grupo  │  │
                        │  │ UC16 Evoluir o encontro        │  │
                        │  └────────────────────────────────┘  │
                        │                                      │
     ┌──────────┐       │  IMPRESSÃO E NÚMEROS                 │
     │          │       │  ┌────────────────────────────────┐  │
     │  Admin.  │───────┼─►│ UC17 Consultar relatórios      │  │
     │          │       │  │ UC18 Emitir cartão             │  │
     └──────────┘       │  │ UC19 Imprimir grades           │  │
                        │  │ UC20 Imprimir prontuário       │  │
                        │  │ UC21 Imprimir resumo do grupo  │  │
                        │  └────────────────────────────────┘  │
                        │                                      │
                        │  CONFIGURAÇÃO                        │
                        │  ┌────────────────────────────────┐  │
                        │  │ UC24 Definir horários de triagem  │
                        │  └────────────────────────────────┘  │
                        │                                      │
                        │  SÓ ADMINISTRADOR                    │
                        │  ┌────────────────────────────────┐  │
                        │  │ UC22 Gerir profissionais       │  │
                        │  │ UC23 Trocar responsável        │  │
                        │  │ UC25 Manter feriados           │  │
                        │  └────────────────────────────────┘  │
                        └──────────────────────────────────────┘
```

O administrador alcança todos os casos de uso. O fisioterapeuta alcança todos
menos UC22, UC23 e UC25, sempre restrito aos próprios pacientes e grupos — a
matriz no fim desta página detalha o escopo de cada um.

## UC01 — Autenticar

**Ator:** ambos.
**Pré-condição:** usuário cadastrado e ativo.

**Fluxo principal**
1. O usuário informa e-mail e senha.
2. O sistema normaliza o e-mail e localiza o usuário.
3. O sistema confere a senha contra o hash.
4. O sistema cria a sessão e redireciona ao painel do perfil.

**Fluxos alternativos**
- Credenciais inválidas: mensagem genérica, sem indicar se o erro foi no e-mail
  ou na senha, e resposta 401.
- Usuário desativado: mesmo tratamento das credenciais inválidas.

## UC02 — Gerir pacientes

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre a lista, que traz apenas os pacientes do seu escopo.
2. Pode buscar por nome, CPF ou data de nascimento.
3. Ao cadastrar, informa nome, CPF, cartão cidadão, nascimento e contato.
4. O sistema valida o CPF pelos dígitos verificadores e verifica duplicidade.
5. O paciente é gravado e vinculado a um responsável.

**Fluxos alternativos**
- CPF inválido ou já cadastrado: formulário devolvido com mensagem e status 400.
- Desativação: o cadastro é marcado como inativo, nunca excluído, porque o
  histórico clínico depende dele.

**Regra:** a queixa clínica não fica no paciente. CID e diagnóstico pertencem ao
ciclo, porque a mesma pessoa pode voltar meses depois com outro problema.

## UC03 — Marcar a avaliação (triagem)

**Ator:** ambos.
**Pré-condição:** paciente cadastrado.

**Fluxo principal**
1. O usuário abre a agenda de triagem, que mostra os horários fixos de cada
   profissional e quais já estão ocupados.
2. Escolhe um horário livre e o paciente.
3. O sistema grava a avaliação.

**Fluxos alternativos**
- **Urgência:** fratura, AVC, pré ou pós-operatório entram fora dos horários
  fixos. O usuário marca a caixa de urgência e informa o motivo, que é
  obrigatório e fica registrado na agenda.
- **Alta na avaliação:** o paciente comparece, é orientado e sai sem tratamento.
  O usuário registra a alta direto na linha da avaliação, e nenhum ciclo é
  aberto.

**Regra:** a avaliação é o primeiro contato e acontece antes de existir ciclo.
Pode não haver ciclo nenhum.

## UC04 — Abrir ciclo de tratamento

**Ator:** ambos.
**Pré-condição:** o paciente já compareceu a uma avaliação.

**Fluxo principal**
1. O usuário escolhe a região, a modalidade, a data da avaliação, o CID, o
   diagnóstico e o total de sessões.
2. O sistema herda o responsável do paciente.
3. O ciclo é aberto com situação ativa.

**Fluxos alternativos**
- Paciente sem avaliação registrada: o sistema recusa e orienta a marcar a
  triagem primeiro.

**Regra:** um paciente pode ter mais de um ciclo ativo, por exemplo joelho e
coluna.

## UC05 — Agendar atendimento

**Ator:** ambos.
**Pré-condição:** paciente cadastrado e, para sessão, ciclo ativo.

**Fluxo principal**
1. O usuário escolhe paciente, tipo, ciclo, data e horário.
2. O sistema verifica: horário dentro da grade, dia útil, data não passada,
   limite de 2 pacientes por profissional no horário, e se o ciclo ainda tem
   sessões disponíveis.
3. O agendamento é criado com situação *Agendado*.

**Fluxos alternativos**
- Qualquer verificação falha: formulário devolvido com a mensagem
  correspondente e status 400.

### UC05.1 — Gerar as sessões do ciclo de uma vez

**Fluxo principal**
1. O usuário escolhe a data da primeira sessão, o horário e os dias da semana.
2. O sistema gera as datas, pulando fim de semana e feriado cadastrado.
3. Antes de gravar, verifica o limite de 2 pacientes por horário em todas as
   datas geradas.
4. Os agendamentos são criados e o sistema informa quais datas foram puladas.

**Fluxos alternativos**
- Alguma data com o horário cheio: nada é gravado e o usuário escolhe outro
  horário ou outros dias.
- Quantidade acima do que falta no ciclo: recusada, com o máximo informado.

## UC06 — Registrar presença

**Ator:** ambos.

**Fluxo principal**
1. Na agenda do dia, o usuário altera a situação do atendimento.
2. Se a situação for *Falta justificada*, informa o motivo.
3. O sistema grava e confirma com um aviso.

**Regras**
- O comparecimento só é aceito a partir do dia da sessão. A **ausência pode ser
  lançada antes**, porque o paciente costuma avisar com antecedência.
- Comparecimento e falta justificada contam como atendimento realizado. Só a
  falta não avisada entra como falta nos números.
- Falta justificada e cancelamento pelo setor geram automaticamente uma sessão
  de reposição ao fim do ciclo. A falta não avisada, não.

## UC07 — Registrar evolução clínica

**Ator:** ambos.
**Pré-condição:** sessão em situação que aceite evolução.

**Fluxo principal**
1. Na ficha do paciente, o usuário abre a evolução da sessão.
2. Informa o que foi realizado, a resposta do paciente e observações.
3. O sistema grava e, se a sessão ainda estava agendada, marca como realizada.

**Fluxos alternativos**
- Sessão com falta, cancelada ou futura: o registro é recusado com explicação.
- Usuário com acesso ao paciente, mas não à sessão: vê em modo somente leitura.

## UC08 — Editar e remarcar o ciclo

**Ator:** ambos.
**Pré-condição:** ciclo ativo.

**Fluxo principal**
1. O usuário corrige região, modalidade, CID, diagnóstico ou total de sessões.
2. Para mudar o dia ou o horário do tratamento, usa *Remarcar*: informa a nova
   data inicial, o horário e os dias da semana.
3. O sistema move as **sessões futuras**, respeitando feriado e limite por
   horário. O que já aconteceu não é tocado.

## UC09 — Encerrar ciclo

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe o motivo: alta, conclusão ou abandono.
2. O sistema grava a situação e a data de alta.

## UC10 — Dar alta ao paciente

**Ator:** ambos.
**Pré-condição:** paciente em acompanhamento.

**Fluxo principal**
1. Na ficha, o usuário informa o motivo da alta.
2. O sistema encerra os ciclos ativos, cancela as sessões futuras e marca o
   paciente como fora de acompanhamento.
3. A ficha passa a exibir a data e o motivo da última alta.

**Regra:** nada é apagado. Cadastro, prontuário e histórico continuam
disponíveis.

## UC11 — Reativar paciente

**Ator:** ambos.
**Pré-condição:** paciente fora de acompanhamento.

**Fluxo principal**
1. O usuário abre a ficha e escolhe *Reativar paciente*.
2. O sistema devolve o paciente ao acompanhamento, com todo o histórico
   anterior.
3. O sistema orienta a conferir telefone e endereço antes de abrir o novo ciclo.

**Regra:** o paciente que volta não é cadastrado de novo. Cadastrar de novo
quebraria o histórico em duas fichas.

## UC12 — Gerir grupos

**Ator:** ambos.

**Fluxo principal**
1. O usuário informa nome, região, dia da semana, horário, capacidade e o
   número de semanas do ciclo do grupo.
2. O sistema verifica que o horário comporta uma sessão de 1 hora e que o
   profissional não conduz outro grupo em horário sobreposto.
3. O grupo é criado.

**Regra:** grupos são desativados, nunca excluídos.

## UC13 — Gerar os encontros do grupo

**Ator:** ambos.
**Pré-condição:** grupo ativo com dia e horário definidos.

**Fluxo principal**
1. O usuário informa a data do primeiro encontro e o número de semanas.
2. O sistema cria um encontro por semana, pulando feriado, e avisa quais datas
   foram puladas.
3. Cada encontro ocupa dois horários seguidos da grade.

**Fluxos alternativos**
- Grupo que já tem encontros marcados: o sistema recusa e pede que os
  existentes sejam cancelados antes, para não montar dois calendários.

## UC14 — Compor o grupo

**Ator:** ambos.
**Pré-condição:** grupo ativo com vaga disponível.

**Fluxo principal**
1. O usuário escolhe um paciente e, opcionalmente, um ciclo ativo dele.
2. O sistema verifica acesso, vaga e se o paciente já está no grupo.
3. A participação é registrada com a data de entrada e o paciente é **inscrito
   em cada encontro já marcado**, o que faz as datas aparecerem no cartão dele.

**Saída:** registrar a saída preenche a data e o motivo, libera a vaga e mantém
o registro. Se o paciente voltar, entra uma participação nova.

## UC15 — Marcar presença no grupo

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre a lista de presença do grupo: inscritos nas linhas, datas nas
   colunas.
2. Marca a situação de cada inscrito no encontro.
3. O sistema grava e confirma.

**Regras**
- Valem as mesmas regras do atendimento individual: o comparecimento espera o
  dia do encontro, a ausência pode ser lançada antes.
- Cada presença vale por duas sessões individuais.
- **No grupo não há reposição:** a data é da turma inteira.
- O bloco do grupo na agenda segura o horário, mas não é atendimento de
  ninguém. Quem conta é a presença de cada inscrito.

## UC16 — Evoluir o encontro do grupo

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre o encontro e escreve a evolução daquele dia.
2. O sistema grava uma evolução para a turma, com a lista de quem esteve
   presente.

**Regra:** a evolução do grupo é uma só, porque a conduta é a mesma para todos.
O que varia por pessoa é a presença.

## UC17 — Consultar relatórios

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe o período: semana, mês ou ano.
2. O sistema apura o **resumo numérico** — realizados, faltas e total no ano,
   separando sessão de avaliação — e os gráficos de horário, região, situação
   e, para o admin, atendimentos por profissional.

**Regras**
- O fisioterapeuta vê apenas os próprios números.
- Comparecimento e falta justificada contam como realizado; só a falta não
  avisada entra na coluna de faltas.
- O bloco do encontro de grupo não é contado: quem conta é a presença de cada
  inscrito.

## UC18 — Emitir o cartão do paciente

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre o cartão do ciclo.
2. O sistema lista as datas numeradas, com dia da semana e horário.
3. O cartão é impresso e entregue ao paciente.

**Regras**
- O cartão é montado a partir da agenda no momento da emissão, então sempre
  reflete eventuais remarcações.
- O cartão de um ciclo de grupo sai identificado como tal, com o nome da turma e
  o encontro semanal, e avisa que não há reposição individual.

## UC19 — Imprimir as grades da semana e do dia

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe a semana ou o dia.
2. O sistema monta a grade no formato das planilhas da clínica, com os horários
   reservados para triagem marcados.
3. A impressão sai sem menu e sem botões, apenas a grade.

**Regra:** o fisioterapeuta imprime a própria grade; o admin escolhe o
profissional ou vê todos no dia.

## UC20 — Imprimir o prontuário

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre o prontuário do paciente.
2. O sistema reúne identificação, tratamentos e as evoluções **separadas por
   ciclo**, em ordem.
3. A folha é impressa e arquivada.

**Regra:** sessões realizadas sem evolução aparecem marcadas, para o
profissional completar antes de arquivar.

## UC21 — Imprimir o resumo do grupo

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre o resumo do grupo.
2. O sistema monta a folha com a identificação da turma, a presença por
   inscrito, o total de sessões equivalentes e a evolução dos encontros.
3. A folha é impressa e anexada ao controle do setor.

## UC22 — Gerir profissionais

**Ator:** administrador.

**Fluxo principal**
1. O admin informa nome, e-mail, senha e perfil.
2. O sistema valida o perfil, o tamanho mínimo da senha e a unicidade do e-mail.
3. O usuário é criado.

**Regra:** o admin não pode desativar a própria conta.

## UC23 — Trocar responsável pelo ciclo

**Ator:** administrador.

**Fluxo principal**
1. O admin escolhe outro profissional ativo.
2. O sistema atualiza o responsável pelo ciclo.

## UC24 — Definir os horários de triagem

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe o dia da semana e o horário.
2. O sistema registra o horário como reservado para triagem.
3. O horário passa a aparecer marcado na grade semanal e a ser oferecido ao
   marcar uma avaliação.

**Regras**
- O fisioterapeuta define apenas os próprios horários. O administrador escolhe
  o profissional e define para qualquer um.
- Tentar gravar horário de outro profissional devolve 403.
- Fora da urgência, a avaliação é marcada em um desses horários.

## UC25 — Manter os feriados

**Ator:** administrador.

**Fluxo principal**
1. O admin escolhe o ano e manda importar os feriados nacionais.
2. O sistema consulta a **BrasilAPI**, grava o que ainda não existe e informa
   quantos foram importados e quantos já estavam cadastrados.

**Fluxos alternativos**
- **Serviço externo indisponível:** o sistema avisa e não altera nada. Os
  feriados já cadastrados continuam valendo e a agenda segue funcionando.
- **Cadastro à mão:** ponto facultativo do servidor, feriado municipal e emenda
  não vêm da API. O admin informa data, nome e tipo. Se o dia já tiver
  atendimento marcado, o sistema diz quantos são — cadastrar o feriado **não
  desmarca ninguém**.
- **Emenda:** quando a secretaria muda a data, o admin remove a antiga e
  cadastra a nova.

**Regra:** o feriado vale para as próximas gerações de sessão. O que já está
agendado permanece até alguém remarcar.

## Matriz de permissões

| Caso de uso | Administrador | Fisioterapeuta |
| --- | --- | --- |
| UC01 Autenticar | sim | sim |
| UC02 Gerir pacientes | todos | apenas os seus |
| UC03 Marcar avaliação | todos | apenas os seus |
| UC04 Abrir ciclo | todos | apenas os seus |
| UC05 Agendar | todos | apenas os seus |
| UC06 Registrar presença | todos | apenas os seus |
| UC07 Registrar evolução | todas | apenas as suas; leitura nas demais do seu paciente |
| UC08 Editar e remarcar ciclo | todos | apenas os seus |
| UC09 Encerrar ciclo | todos | apenas os seus |
| UC10 Dar alta ao paciente | todos | apenas os seus |
| UC11 Reativar paciente | todos | apenas os seus |
| UC12 Gerir grupos | todos | apenas os que conduz |
| UC13 Gerar encontros | todos | apenas os que conduz |
| UC14 Compor grupo | qualquer paciente | apenas os seus pacientes |
| UC15 Marcar presença no grupo | todos | apenas os que conduz |
| UC16 Evoluir o encontro | todos | apenas os que conduz |
| UC17 Relatórios | clínica inteira | apenas os seus números |
| UC18 Emitir cartão | todos | apenas os seus |
| UC19 Imprimir grades | qualquer profissional | apenas a sua |
| UC20 Imprimir prontuário | todos | apenas os seus |
| UC21 Imprimir resumo do grupo | todos | apenas os que conduz |
| UC22 Gerir profissionais | sim | não |
| UC23 Trocar responsável | sim | não |
| UC24 Definir horários de triagem | qualquer profissional | apenas os seus |
| UC25 Manter feriados | sim | não |
