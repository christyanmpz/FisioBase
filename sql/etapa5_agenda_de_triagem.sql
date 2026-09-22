-- ---------------------------------------------------------------------
-- Etapa 5 — agenda de triagem separada
--
-- Rodar ANTES de publicar o código da etapa 5.
--
-- Uma tabela nova e nada mais: a versão que está no ar não a conhece,
-- então dá para rodar com o sistema funcionando.
--
-- Cada profissional reserva alguns horários da semana para o primeiro
-- contato com o paciente — na planilha da clínica são as células marcadas
-- com "T =". A avaliação é agendada nesses horários; fratura, AVC e
-- pré/pós-operatório entram como urgência, encaixados fora deles.
--
-- Tudo dentro de uma transação. Se qualquer linha falhar, nada é gravado.
-- ---------------------------------------------------------------------

BEGIN;

CREATE TABLE IF NOT EXISTS horarios_triagem (
    id                serial PRIMARY KEY,
    fisioterapeuta_id integer NOT NULL REFERENCES usuarios (id),
    dia_semana        smallint NOT NULL,
    hora              time NOT NULL,
    ativo             boolean NOT NULL DEFAULT true,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_triagem_slot UNIQUE (fisioterapeuta_id, dia_semana, hora),
    CONSTRAINT chk_triagem_dia CHECK (dia_semana >= 0 AND dia_semana <= 6)
);

CREATE INDEX IF NOT EXISTS ix_triagem_profissional
    ON horarios_triagem (fisioterapeuta_id, dia_semana, hora);

COMMIT;
