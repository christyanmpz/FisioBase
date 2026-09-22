-- ---------------------------------------------------------------------
-- Etapa 4B — evolução do grupo e motivo da saída
--
-- Rodar ANTES de publicar o código da etapa 4B.
--
-- Duas mudanças, as duas só acrescentam:
--   1. grupo_pacientes.motivo_saida — por que o paciente saiu antes do fim.
--   2. evolucoes_grupo — uma anotação por encontro do grupo.
--
-- Nada que já existe é alterado ou removido, então dá para rodar com o
-- sistema no ar: a versão que está publicada não lê nenhuma das duas.
--
-- Por que uma tabela separada e não a evolucoes que já existe: aquela
-- exige paciente_id, porque é a evolução de um atendimento individual.
-- No grupo o profissional relata o encontro inteiro — os exercícios são
-- os mesmos para todos os inscritos — e o que muda por pessoa é só a
-- presença, que continua registrada em agendamentos.
--
-- Tudo dentro de uma transação. Se qualquer linha falhar, nada é gravado.
-- ---------------------------------------------------------------------

BEGIN;

-- 1. Motivo da saída do grupo: entra na alta e no histórico do paciente.
ALTER TABLE grupo_pacientes
    ADD COLUMN IF NOT EXISTS motivo_saida text;

-- 2. Evolução do encontro. A chave única por (grupo, data) garante uma
--    anotação por encontro: salvar de novo corrige, não duplica.
CREATE TABLE IF NOT EXISTS evolucoes_grupo (
    id                serial PRIMARY KEY,
    grupo_id          integer NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    agendamento_id    integer REFERENCES agendamentos (id),
    fisioterapeuta_id integer NOT NULL REFERENCES usuarios (id),
    data              date NOT NULL,
    descricao         text,
    observacoes       text,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_evo_grupo_data UNIQUE (grupo_id, data)
);

CREATE INDEX IF NOT EXISTS ix_evo_grupo_grupo
    ON evolucoes_grupo (grupo_id, data);

COMMIT;
