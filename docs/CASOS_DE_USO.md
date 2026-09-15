# Casos de uso

## Atores

| Ator | Descrição |
| --- | --- |
| **Administrador** | Coordena o setor. Cadastra profissionais, enxerga todos os pacientes, agendas e relatórios, e redireciona tratamentos entre profissionais. |
| **Fisioterapeuta** | Atende pacientes. Enxerga apenas os próprios pacientes, ciclos, agendamentos e os grupos que conduz. |

## Diagrama

```
                        ┌─────────────────────────────────┐
                        │           FisioBase             │
                        │                                 │
                        │   ┌───────────────────────┐     │
     ┌──────────┐       │   │ UC01 Autenticar       │     │
     │          │───────┼──►│ UC02 Gerir pacientes  │     │
     │  Fisio-  │       │   │ UC03 Abrir ciclo      │     │
     │terapeuta │───────┼──►│ UC04 Agendar          │     │
     │          │       │   │ UC05 Registrar presença│    │
     └──────────┘       │   │ UC06 Registrar evolução│    │
                        │   │ UC07 Encerrar ciclo   │     │
                        │   │ UC08 Gerir grupos     │     │
                        │   │ UC09 Compor grupo     │     │
     ┌──────────┐       │   │ UC10 Consultar        │     │
     │  Admin.  │───────┼──►│      relatórios       │     │
     │          │       │   │ UC11 Gerir profissionais    │
     └──────────┘       │   │ UC12 Trocar responsável│    │
                        │   │ UC13 Gerar sessões    │     │
                        │   │ UC14 Emitir cartão    │     │
                        │   │ UC15 Imprimir grades  │     │
                        │   │ UC16 Imprimir prontuário    │
                        │   └───────────────────────┘     │
                        └─────────────────────────────────┘

     UC11 e UC12: exclusivos do administrador.
     Demais: ambos os atores, com escopo de dados diferente.
```

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
2. Pode buscar por nome ou CPF.
3. Ao cadastrar, informa nome, CPF, contato, CID e diagnóstico.
4. O sistema valida o CPF pelos dígitos verificadores e verifica duplicidade.
5. O paciente é gravado e vinculado a um responsável.

**Fluxos alternativos**
- CPF inválido ou já cadastrado: formulário devolvido com mensagem e status 400.
- Desativação: o cadastro é marcado como inativo, nunca excluído, porque o
  histórico clínico depende dele.

## UC03 — Abrir ciclo de tratamento

**Ator:** ambos.
**Pré-condição:** paciente cadastrado.

**Fluxo principal**
1. O usuário escolhe a região, a modalidade, a data da avaliação e o total de
   sessões.
2. O sistema herda o responsável do paciente.
3. O ciclo é aberto com situação ativa.

**Regra:** um paciente pode ter mais de um ciclo ativo, por exemplo joelho e
coluna.

## UC04 — Agendar atendimento

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

## UC05 — Registrar presença

**Ator:** ambos.

**Fluxo principal**
1. Na agenda do dia, o usuário altera a situação do atendimento.
2. O sistema grava e confirma com um aviso.

**Regra:** presença e falta só são aceitas a partir do dia da sessão.
Confirmação e cancelamento valem para qualquer data.

## UC06 — Registrar evolução clínica

**Ator:** ambos.
**Pré-condição:** sessão em situação que aceite evolução.

**Fluxo principal**
1. Na ficha do paciente, o usuário abre a evolução da sessão.
2. Informa o que foi realizado, a resposta do paciente e observações.
3. O sistema grava e, se a sessão ainda estava agendada, marca como realizada.

**Fluxos alternativos**
- Sessão com falta, cancelada ou futura: o registro é recusado com explicação.
- Usuário com acesso ao paciente, mas não à sessão: vê em modo somente leitura.

## UC07 — Encerrar ciclo

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe o motivo: alta, conclusão ou abandono.
2. O sistema grava a situação e a data de alta.

## UC08 — Gerir grupos

**Ator:** ambos.

**Fluxo principal**
1. O usuário informa nome, região, dia da semana, horário e capacidade.
2. O sistema verifica que o horário comporta uma sessão de 1 hora e que o
   profissional não conduz outro grupo em horário sobreposto.
3. O grupo é criado.

**Regra:** grupos são desativados, nunca excluídos.

## UC09 — Compor grupo

**Ator:** ambos.
**Pré-condição:** grupo ativo com vaga disponível.

**Fluxo principal**
1. O usuário escolhe um paciente e, opcionalmente, um ciclo ativo dele.
2. O sistema verifica acesso, vaga e se o paciente já está no grupo.
3. A participação é registrada com a data de entrada.

**Saída:** registrar a saída preenche a data e libera a vaga, sem apagar o
registro. Se o paciente voltar, entra uma participação nova.

## UC10 — Consultar relatórios

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe mês e ano.
2. O sistema apura atendimentos por horário, queixas por região, situação dos
   agendamentos e, para o admin, atendimentos por profissional.

**Regra:** o fisioterapeuta vê apenas os próprios números.

## UC11 — Gerir profissionais

**Ator:** administrador.

**Fluxo principal**
1. O admin informa nome, e-mail, senha e perfil.
2. O sistema valida o perfil, o tamanho mínimo da senha e a unicidade do e-mail.
3. O usuário é criado.

**Regra:** o admin não pode desativar a própria conta.

## UC12 — Trocar responsável pelo ciclo

**Ator:** administrador.

**Fluxo principal**
1. O admin escolhe outro profissional ativo.
2. O sistema atualiza o responsável pelo ciclo.

## UC13 — Gerar as sessões do ciclo

**Ator:** ambos.
**Pré-condição:** ciclo ativo com sessões a agendar.

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

## UC14 — Emitir o cartão do paciente

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre o cartão do ciclo.
2. O sistema lista as datas numeradas, com dia da semana e horário.
3. O cartão é impresso e entregue ao paciente.

**Regra:** o cartão é montado a partir da agenda no momento da emissão, então
sempre reflete eventuais remarcações.

## UC15 — Imprimir as grades da semana e do dia

**Ator:** ambos.

**Fluxo principal**
1. O usuário escolhe a semana ou o dia.
2. O sistema monta a grade no formato das planilhas da clínica.
3. A impressão sai sem menu e sem botões, apenas a grade.

**Regra:** o fisioterapeuta imprime a própria grade; o admin escolhe o
profissional ou vê todos no dia.

## UC16 — Imprimir o prontuário

**Ator:** ambos.

**Fluxo principal**
1. O usuário abre o prontuário do paciente.
2. O sistema reúne identificação, tratamentos e todas as evoluções em ordem.
3. A folha é impressa e arquivada.

**Regra:** sessões realizadas sem evolução aparecem marcadas, para o
profissional completar antes de arquivar.

## Matriz de permissões

| Caso de uso | Administrador | Fisioterapeuta |
| --- | --- | --- |
| UC01 Autenticar | sim | sim |
| UC02 Gerir pacientes | todos | apenas os seus |
| UC03 Abrir ciclo | todos | apenas os seus |
| UC04 Agendar | todos | apenas os seus |
| UC05 Registrar presença | todos | apenas os seus |
| UC06 Registrar evolução | todas | apenas as suas; leitura nas demais do seu paciente |
| UC07 Encerrar ciclo | todos | apenas os seus |
| UC08 Gerir grupos | todos | apenas os que conduz |
| UC09 Compor grupo | qualquer paciente | apenas os seus pacientes |
| UC10 Relatórios | clínica inteira | apenas os seus números |
| UC11 Gerir profissionais | sim | não |
| UC12 Trocar responsável | sim | não |
| UC13 Gerar sessões | todos os ciclos | apenas os seus |
| UC14 Emitir cartão | todos | apenas os seus |
| UC15 Imprimir grades | qualquer profissional | apenas a sua |
| UC16 Imprimir prontuário | todos | apenas os seus |