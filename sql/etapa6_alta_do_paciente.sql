-- ---------------------------------------------------------------------
-- Etapa 6 — alta do paciente com histórico e reativação
--
-- Rodar ANTES de publicar o código da etapa 6.
--
-- Duas colunas novas em pacientes, e nada mais. A versão que está no ar
-- não as conhece, então dá para rodar com o sistema funcionando.
--
-- Sair da clínica passa a ser alta, não exclusão: o cadastro e todo o
-- histórico continuam, e o paciente pode voltar sem recadastro. `ativo`
-- continua dizendo se ele está em acompanhamento hoje; as duas colunas
-- guardam quando e por que ele saiu da última vez.
--
-- Tudo dentro de uma transação. Se qualquer linha falhar, nada é gravado.
-- ---------------------------------------------------------------------

BEGIN;

ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS data_alta date;

ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS motivo_alta text;

-- Quem já estava inativo antes desta etapa saiu sem motivo registrado.
-- A linha abaixo deixa isso explícito, em vez de um campo vazio sem
-- explicação no histórico.
UPDATE pacientes
   SET motivo_alta = 'Alta registrada antes de o sistema guardar o motivo.'
 WHERE ativo = false
   AND motivo_alta IS NULL;

COMMIT;
