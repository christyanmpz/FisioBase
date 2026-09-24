# Requisitos

Levantados junto ao setor de fisioterapia, a partir da rotina atual em fichas
de papel e planilhas Excel, e revisados com a clínica em 19/09/2026.

Dos dez itens do primeiro levantamento, todos foram atendidos. A revisão de
setembro trouxe mais nove pedidos, todos implementados. Os dois requisitos que
seguem como trabalho futuro dependem de decisões que ainda não são só técnicas
e estão justificados no fim desta página.

## Requisitos funcionais

### Primeiro levantamento

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
| RF13 | Lista de presença das sessões de grupo | Implementado |
| RF14 | Disponibilidade do profissional: horários fixos de triagem | Implementado |
| RF15 | Geração automática das datas do ciclo, pulando feriados | Implementado |
| RF16 | Impressão do cartão do paciente com as datas agendadas | Implementado |
| RF17 | Impressão da grade semanal por profissional e da grade diária do setor | Implementado |
| RF18 | Reativação do cadastro com histórico de tratamentos anteriores | Implementado |
| RF19 | Registro de falta justificada com o motivo da ausência | Implementado |
| RF20 | Impressão do prontuário completo e da folha de evolução | Implementado |
| RF21 | Paginação e busca com sugestões na lista de pacientes | Implementado |

### Revisão de setembro de 2026

| Código | Requisito | Situação |
| --- | --- | --- |
| RF22 | Ausência lançada antes do dia, porque o paciente avisa com antecedência | Implementado |
| RF23 | Reposição criada automaticamente ao fim do ciclo, para falta justificada e cancelamento | Implementado |
| RF24 | Histórico do paciente separado por ciclo de tratamento | Implementado |
| RF25 | Busca de paciente também pela data de nascimento | Implementado |
| RF26 | Resumo numérico do mês e do ano, no formato que a clínica soma à mão | Implementado |
| RF27 | Cartão cidadão no cadastro do paciente | Implementado |
| RF28 | CID e diagnóstico registrados no ciclo, não no paciente | Implementado |
| RF29 | Edição do ciclo e remarcação das sessões futuras | Implementado |
| RF30 | Encontros de grupo gerados por semana, com inscrição vinculada ao ciclo | Implementado |
| RF31 | Evolução do encontro de grupo, escrita uma vez para a turma | Implementado |
| RF32 | Motivo registrado na saída do grupo | Implementado |
| RF33 | Resumo do grupo impresso, com presença por inscrito | Implementado |
| RF34 | Agenda de triagem com horários fixos por profissional | Implementado |
| RF35 | Avaliação de urgência fora dos horários fixos, com motivo obrigatório | Implementado |
| RF36 | Alta direto na avaliação, sem abrir ciclo | Implementado |
| RF37 | Alta do paciente com motivo, encerrando ciclos e cancelando sessões futuras | Implementado |
| RF38 | Ciclo só pode ser aberto depois de o paciente comparecer a uma avaliação | Implementado |
| RF39 | Importação dos feriados nacionais de uma fonte externa | Implementado |
| RF40 | Cadastro de ponto facultativo, feriado municipal e emenda | Implementado |

### Trabalho futuro

| Código | Requisito | Por que não foi feito |
| --- | --- | --- |
| RF41 | Consulta pública das próprias datas por link, sem login | Expor dado de paciente em link aberto é risco de LGPD. Precisa de decisão da clínica sobre o que mostrar e por quanto tempo o link vale |
| RF42 | Integração com Google Agenda e envio de lembrete por e-mail | Depende de conta institucional e de política sobre mensagem automática a paciente |

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
| RNF09 | As regras de negócio devem ser verificáveis automaticamente | 454 testes automatizados com pytest |
| RNF10 | Alterações não podem quebrar o que já funciona | Testes rodam antes de cada publicação |
| RNF11 | Listas longas não podem degradar a navegação | Paginação de 20 por página e busca com sugestões |
| RNF12 | As folhas impressas devem sair sem os elementos de navegação | Folha de estilo específica para impressão |
| RNF13 | O texto deve ser legível em monitor comum, não só em tela boa | Contraste mínimo de 4,5:1 (WCAG AA), verificado por teste |
| RNF14 | Situações diferentes devem ser distinguíveis na tela | Uma cor por situação do atendimento, verificada por teste |
| RNF15 | Uma indisponibilidade de serviço externo não pode parar o sistema | A importação de feriados avisa e o sistema segue com o que já tem |

## Regras de negócio

| Código | Regra |
| --- | --- |
| RN01 | Expediente de 07:30 às 15:30, sessões de 30 minutos, encerrando às 16h. São 16 horários por dia; as 12:00 ficam fora da grade, para o almoço |
| RN02 | Atendimento de segunda a sexta-feira |
| RN03 | No máximo 2 pacientes por profissional no mesmo horário |
| RN04 | Ciclo com até 30 sessões; o padrão da clínica é 10 |
| RN05 | A numeração da sessão conta apenas os atendimentos realizados, o que permite reposição |
| RN06 | Um paciente pode ter mais de um ciclo ativo ao mesmo tempo |
| RN07 | Comparecimento só é registrado a partir do dia da sessão. Ausência pode ser lançada antes, porque o paciente avisa com antecedência |
| RN08 | Não há evolução em sessão com falta, cancelada ou de data futura |
| RN09 | Podem editar a evolução: o autor, o responsável pela sessão e o administrador |
| RN10 | A sessão de grupo dura 1 hora e equivale a duas sessões individuais |
| RN11 | Grupos têm capacidade de 1 a 20 participantes, com 14 de padrão, organizados por região |
| RN12 | O mesmo profissional não pode conduzir dois grupos em horários sobrepostos |
| RN13 | Pacientes e grupos são desativados, nunca excluídos |
| RN14 | A saída do grupo preserva o registro, para manter o histórico de presença |
| RN15 | Comparecimento e falta justificada contam como atendimento realizado. Só a falta não avisada entra na coluna de faltas |
| RN16 | A falta justificada e o cancelamento pelo setor dão direito a uma sessão de reposição ao fim do ciclo. A falta não avisada, não |
| RN17 | A geração automática pula fim de semana e feriado cadastrado |
| RN18 | A geração respeita o total de sessões do ciclo e o limite por horário |
| RN19 | O ciclo de tratamento só é aberto depois de o paciente comparecer a uma avaliação |
| RN20 | A avaliação pode terminar em alta, sem abrir ciclo nenhum, quando o paciente sai orientado |
| RN21 | A alta do paciente encerra os ciclos ativos e cancela as sessões futuras, preservando todo o histórico |
| RN22 | O encontro de grupo tem data fixa da turma: não há reposição individual |
| RN23 | O bloco do grupo na agenda segura o horário, mas não é atendimento. Quem conta é a presença de cada inscrito |
| RN24 | Fora da urgência, a avaliação é marcada em um dos horários fixos de triagem do profissional |
| RN25 | A urgência é encaixe fora da grade de triagem e exige o motivo registrado |

## Rastreabilidade

Cada regra e cada requisito tem teste automatizado. Os arquivos com nome mais
direto:

| Assunto | Arquivo de teste |
| --- | --- |
| RN07, RN15, RN16 — ausência, falta justificada e reposição | `test_falta_justificada.py`, `test_reposicao.py` |
| RN19, RN20, RN21 — alta e reativação | `test_alta_paciente.py` |
| RN22, RN23 — grupo | `test_grupo_sessoes.py`, `test_grupo_gestao.py` |
| RN24, RN25 — triagem | `test_triagem.py` |
| RN17 e RF39, RF40 — feriados e integração | `test_feriados.py` |
| RNF13, RNF14 — contraste e cores | `test_contraste_e_avisos.py`, `test_visual_situacoes.py` |
