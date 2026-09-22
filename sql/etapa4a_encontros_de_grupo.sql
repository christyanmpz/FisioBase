-- ---------------------------------------------------------------------
-- Etapa 4A — o grupo passa a ter encontros e lista de presença
--
-- Rodar ANTES de publicar o código da etapa 4A.
--
-- Duas mudanças:
--   1. grupos.total_semanas — quantas semanas o tratamento em grupo dura.
--   2. chk_ag_alvo — passa a aceitar a presença de um paciente num
--      encontro de grupo, que é uma linha com paciente E grupo juntos.
--
-- Por que mexer na chk_ag_alvo: hoje ela exige "ou paciente, ou grupo".
-- Isso cobria dois casos — o atendimento individual e o bloco do grupo na
-- agenda. Falta o terceiro: a presença de cada inscrito em cada data do
-- grupo. Registrando essa presença como agendamento, tudo que já existe
-- passa a funcionar para o grupo sem código novo: os status de presença,
-- o histórico do paciente, o cartão, os relatórios e os gráficos.
--
-- A regra nova continua fechada, não é um "vale tudo":
--   tipo GRUPO      -> grupo sim, paciente não   (o bloco na agenda)
--   tipo SESSAO     -> paciente sim; grupo opcional (individual ou presença)
--   tipo AVALIACAO  -> paciente sim
--
-- Tudo dentro de uma transação. Se qualquer linha falhar, nada é gravado.
-- A troca da restrição valida as linhas que já existem: se alguma não
-- couber na regra nova, o banco recusa e desfaz tudo.
-- ---------------------------------------------------------------------

BEGIN;

-- 1. Duração do tratamento em grupo. O padrão da clínica são 6 semanas de
--    1 hora, equivalentes a 12 sessões individuais.
ALTER TABLE grupos
    ADD COLUMN IF NOT EXISTS total_semanas integer NOT NULL DEFAULT 6;

ALTER TABLE grupos
    DROP CONSTRAINT IF EXISTS chk_grupo_semanas;

ALTER TABLE grupos
    ADD CONSTRAINT chk_grupo_semanas
    CHECK (total_semanas >= 1 AND total_semanas <= 52);

-- 2. O agendamento passa a aceitar a presença no grupo.
ALTER TABLE agendamentos
    DROP CONSTRAINT IF EXISTS chk_ag_alvo;

ALTER TABLE agendamentos
    ADD CONSTRAINT chk_ag_alvo
    CHECK (
        (tipo = 'GRUPO' AND grupo_id IS NOT NULL AND paciente_id IS NULL)
        OR (tipo <> 'GRUPO' AND paciente_id IS NOT NULL)
    );

COMMIT;
