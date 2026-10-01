-- ---------------------------------------------------------------------
-- Etapa 7 — a avaliação que justifica o ciclo
--
-- Rodar ANTES de publicar o código da etapa 7.
--
-- Uma coluna nova em ciclos_tratamento, e nada mais. A versão que está no
-- ar não a conhece, então dá para rodar com o sistema funcionando.
--
-- Hoje o ciclo guarda `data_avaliacao`, uma data digitada à mão: ela diz
-- quando foi a avaliação, mas não aponta para avaliação nenhuma. A clínica
-- pediu que o tratamento referencie a avaliação que o justifica.
--
-- A coluna aceita NULO de propósito, por dois motivos:
--
--   1. Os ciclos que já existem não têm como saber a qual avaliação
--      pertencem. Adivinhar pela data erraria onde houvesse duas
--      avaliações no mesmo dia, e vínculo errado em prontuário é pior que
--      vínculo vazio. Eles ficam sem, e quem quiser corrige pelo Editar.
--
--   2. O ciclo de grupo não tem avaliação própria: no grupo ela acontece
--      no primeiro encontro. Esses ciclos seguem sem vínculo para sempre.
--
-- ON DELETE SET NULL: se um dia um agendamento de avaliação for apagado,
-- o ciclo perde o vínculo mas continua existindo. O contrário — apagar o
-- tratamento junto — seria perder prontuário por tabela.
--
-- Uma mesma avaliação PODE justificar mais de um ciclo, por decisão da
-- clínica: o paciente é avaliado uma vez e o fisioterapeuta encontra dois
-- problemas. Por isso não há restrição de unicidade aqui.
--
-- Tudo dentro de uma transação. Se qualquer linha falhar, nada é gravado.
-- ---------------------------------------------------------------------

BEGIN;

ALTER TABLE ciclos_tratamento
    ADD COLUMN IF NOT EXISTS avaliacao_id integer;

-- A restrição é criada à parte para o script poder rodar duas vezes sem
-- estourar: ADD COLUMN IF NOT EXISTS não cobre a chave estrangeira.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_ciclo_avaliacao'
    ) THEN
        ALTER TABLE ciclos_tratamento
            ADD CONSTRAINT fk_ciclo_avaliacao
            FOREIGN KEY (avaliacao_id)
            REFERENCES agendamentos (id)
            ON DELETE SET NULL;
    END IF;
END
$$;

-- A busca mais comum é "quais ciclos saíram desta avaliação".
CREATE INDEX IF NOT EXISTS ix_ciclos_avaliacao
    ON ciclos_tratamento (avaliacao_id);

COMMIT;

-- ---------------------------------------------------------------------
-- Conferência — rode depois do COMMIT, fora da transação.
--
-- 1. A coluna e a restrição existem?
--
--    SELECT column_name, data_type, is_nullable
--      FROM information_schema.columns
--     WHERE table_name = 'ciclos_tratamento'
--       AND column_name = 'avaliacao_id';
--
--    SELECT conname, confdeltype
--      FROM pg_constraint
--     WHERE conname = 'fk_ciclo_avaliacao';
--
--    O confdeltype deve vir 'n', que é o código de SET NULL.
--
-- 2. Quantos ciclos existem, e quantos vão ficar sem vínculo?
--
--    SELECT modalidade,
--           count(*) AS ciclos,
--           count(avaliacao_id) AS com_vinculo
--      FROM ciclos_tratamento
--     GROUP BY modalidade;
--
--    Logo depois de rodar, com_vinculo vem zero em todos: é o esperado.
-- ---------------------------------------------------------------------
