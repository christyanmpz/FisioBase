-- ---------------------------------------------------------------------
-- Etapa 3 — cartão cidadão no paciente, CID e diagnóstico no ciclo
--
-- Rodar ANTES de publicar o código da etapa 3. As colunas novas não são
-- lidas pela versão que está no ar, então dá para rodar com o sistema
-- funcionando: ninguém fica sem atendimento durante a migração.
--
-- Tudo dentro de uma transação. Se qualquer linha falhar, nada é gravado.
-- ---------------------------------------------------------------------

BEGIN;

-- 1. Cartão cidadão: identificação oficial do paciente no município.
--    Opcional, porque nem todo paciente tem.
ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS cartao_cidadao varchar(15);

-- 2. CID e diagnóstico passam a viver no ciclo: cada tratamento trata de
--    uma queixa diferente, e o mesmo paciente pode voltar anos depois por
--    outro motivo.
ALTER TABLE ciclos_tratamento
    ADD COLUMN IF NOT EXISTS cid varchar(30);

ALTER TABLE ciclos_tratamento
    ADD COLUMN IF NOT EXISTS diagnostico text;

-- 3. O banco também garante o formato do cartão, não só o formulário.
ALTER TABLE pacientes
    DROP CONSTRAINT IF EXISTS chk_pac_cartao;

ALTER TABLE pacientes
    ADD CONSTRAINT chk_pac_cartao
    CHECK (cartao_cidadao IS NULL OR cartao_cidadao ~ '^[0-9]{10,15}$');

-- 4. Copia para os ciclos o CID e o diagnóstico que hoje estão no cadastro
--    do paciente. Só mexe em ciclo que ainda está vazio nos dois campos,
--    então rodar de novo não sobrescreve nada digitado depois.
UPDATE ciclos_tratamento c
   SET cid = p.cid,
       diagnostico = p.diagnostico
  FROM pacientes p
 WHERE c.paciente_id = p.id
   AND c.cid IS NULL
   AND c.diagnostico IS NULL
   AND (p.cid IS NOT NULL OR p.diagnostico IS NOT NULL);

-- 5. A partir da etapa 3 o sistema não escreve mais nessas duas colunas do
--    paciente. Elas ficam como histórico, mas precisam aceitar nulo para
--    que o cadastro de paciente novo continue funcionando.
--    Em coluna que já aceita nulo, estas duas linhas não fazem nada.
ALTER TABLE pacientes ALTER COLUMN cid DROP NOT NULL;
ALTER TABLE pacientes ALTER COLUMN diagnostico DROP NOT NULL;

COMMIT;
