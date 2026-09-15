# Requisitos

Levantados junto ao setor de fisioterapia, a partir da rotina atual em fichas
de papel e planilhas Excel.

## Requisitos funcionais

| Código | Requisito | Situação |
| --- | --- | --- |
| RF01 | Cadastro de pacientes com validação de CPF e busca por nome ou CPF | Implementado |
| RF02 | Cadastro de profissionais, restrito ao administrador | Implementado |
| RF03 | Controle de acesso por perfil, com escopo de dados por profissional | Implementado |
| RF04 | Ciclo de tratamento ligando avaliação e sessões | Implementado |
| RF05 | Agenda de avaliações e sessões, com expediente e limite por horário | Implementado |
| RF06 | Registro de presença, falta e cancelamento | Implementado |
| RF07 | Numeração de sessão que permite reposição | Implementado |
| RF08 | Evolução clínica por sessão, editável, com controle de autoria | Implementado |
| RF09 | Registro de alta com motivo e data | Implementado |
| RF10 | Grupos terapêuticos com horário fixo semanal e capacidade | Implementado |
| RF11 | Composição do grupo com histórico de entrada e saída | Implementado |
| RF12 | Relatório mensal com gráficos de presença, horário e região | Implementado |
| RF13 | Lista de presença das sessões de grupo | Trabalho futuro |
| RF14 | Disponibilidade do profissional: triagens fixas, reunião e horários fechados | Trabalho futuro |
| RF15 | Geração automática das datas do ciclo, pulando feriados | Trabalho futuro |
| RF16 | Impressão do cartão do paciente com as datas agendadas | Trabalho futuro |
| RF17 | Impressão da grade semanal por profissional e da grade diária do setor | Trabalho futuro |
| RF18 | Reativação do cadastro com histórico de tratamentos anteriores | Trabalho futuro |

## Requisitos não funcionais

| Código | Requisito | Como foi atendido |
| --- | --- | --- |
| RNF01 | As senhas não podem ser armazenadas em texto puro | Hash com `werkzeug.security` |
| RNF02 | O sistema deve impedir acesso a prontuário de paciente de outro profissional | `acessivel_por()` nos modelos e filtros por perfil |
| RNF03 | Formulários protegidos contra falsificação de requisição | Token CSRF obrigatório via Flask-WTF |
| RNF04 | Segredos não podem ser versionados | `.env` no `.gitignore`; variáveis na plataforma |
| RNF05 | A aplicação não pode subir com configuração incompleta | `RuntimeError` se faltar variável de ambiente |
| RNF06 | Datas devem respeitar o fuso do Brasil, mesmo com servidor em UTC | Função `hoje()` com `America/Sao_Paulo` |
| RNF07 | O sistema deve ser acessível pelo navegador, sem instalação | Aplicação web publicada na Vercel |
| RNF08 | A interface deve funcionar em tela pequena | Layout responsivo, com barra lateral adaptável |
| RNF09 | As regras de negócio devem ser verificáveis automaticamente | 144 testes automatizados com pytest |
| RNF10 | Alterações não podem quebrar o que já funciona | Testes rodam antes de cada publicação |

## Regras de negócio

| Código | Regra |
| --- | --- |
| RN01 | Expediente de 07:30 às 15:30, sessões de 30 minutos, encerrando às 16h |
| RN02 | Atendimento de segunda a sexta-feira |
| RN03 | No máximo 2 pacientes por profissional no mesmo horário |
| RN04 | Ciclo com até 30 sessões; o padrão da clínica é 10 |
| RN05 | A numeração da sessão conta apenas os atendimentos realizados, o que permite reposição |
| RN06 | Um paciente pode ter mais de um ciclo ativo ao mesmo tempo |
| RN07 | Presença e falta só podem ser registradas a partir do dia da sessão |
| RN08 | Não há evolução em sessão com falta, cancelada ou de data futura |
| RN09 | Podem editar a evolução: o autor, o responsável pela sessão e o administrador |
| RN10 | A sessão de grupo dura 1 hora e equivale a duas sessões individuais |
| RN11 | Grupos têm de 12 a 14 participantes, organizados por região |
| RN12 | O mesmo profissional não pode conduzir dois grupos em horários sobrepostos |
| RN13 | Pacientes e grupos são desativados, nunca excluídos |
| RN14 | A saída do grupo preserva o registro, para manter o histórico de presença |