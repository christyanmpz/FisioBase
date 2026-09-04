-- ============================================================
-- FisioBase — esquema PostgreSQL (Supabase)
-- Rodar UMA VEZ no SQL Editor do Supabase.
-- ============================================================

-- ------------------------------------------------------------
-- 1. USUARIOS
-- ------------------------------------------------------------
CREATE TABLE usuarios (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(150) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    senha_hash      VARCHAR(255) NOT NULL,
    perfil          VARCHAR(30)  NOT NULL DEFAULT 'FISIOTERAPEUTA',
    ativo           BOOLEAN      NOT NULL DEFAULT TRUE,
    -- proteção contra força bruta (serverless não guarda estado em memória)
    falhas_login    INTEGER      NOT NULL DEFAULT 0,
    bloqueado_ate   TIMESTAMPTZ,
    criado_em       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_perfil CHECK (perfil IN ('ADMIN', 'FISIOTERAPEUTA'))
);

-- ------------------------------------------------------------
-- 2. PACIENTES
-- ------------------------------------------------------------
CREATE TABLE pacientes (
    id                 SERIAL PRIMARY KEY,
    nome               VARCHAR(150) NOT NULL,
    cpf                VARCHAR(14) UNIQUE,
    data_nascimento    DATE,
    telefone           VARCHAR(30),
    email              VARCHAR(150),
    endereco           VARCHAR(255),
    cid                VARCHAR(30),
    diagnostico        TEXT,
    observacoes        TEXT,
    ativo              BOOLEAN NOT NULL DEFAULT TRUE,
    fisioterapeuta_id  INTEGER REFERENCES usuarios(id),
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pacientes_nome  ON pacientes(nome);
CREATE INDEX idx_pacientes_fisio ON pacientes(fisioterapeuta_id);

-- ------------------------------------------------------------
-- 3. CICLOS DE TRATAMENTO
-- Amarra avaliação + até 10 sessões. É o que responde
-- "em que sessão do ciclo este paciente está?".
-- ------------------------------------------------------------
CREATE TABLE ciclos_tratamento (
    id                 SERIAL PRIMARY KEY,
    paciente_id        INTEGER NOT NULL REFERENCES pacientes(id),
    fisioterapeuta_id  INTEGER NOT NULL REFERENCES usuarios(id),
    regiao             VARCHAR(30),
    modalidade         VARCHAR(20) NOT NULL DEFAULT 'INDIVIDUAL',
    data_avaliacao     DATE NOT NULL,
    total_sessoes      INTEGER NOT NULL DEFAULT 10,
    status             VARCHAR(20) NOT NULL DEFAULT 'ATIVO',
    data_alta          DATE,
    observacoes        TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_ciclo_regiao     CHECK (regiao IN ('OMBRO','JOELHO','COLUNA','OUTRO')),
    CONSTRAINT chk_ciclo_modalidade CHECK (modalidade IN ('INDIVIDUAL','GRUPO')),
    CONSTRAINT chk_ciclo_status     CHECK (status IN ('ATIVO','CONCLUIDO','ALTA','ABANDONO'))
);
CREATE INDEX idx_ciclos_paciente ON ciclos_tratamento(paciente_id);
CREATE INDEX idx_ciclos_status   ON ciclos_tratamento(status);

-- ------------------------------------------------------------
-- 4. GRUPOS  (12 a 14 pessoas, por região)
-- ------------------------------------------------------------
CREATE TABLE grupos (
    id                 SERIAL PRIMARY KEY,
    nome               VARCHAR(100) NOT NULL,
    regiao             VARCHAR(30)  NOT NULL,
    fisioterapeuta_id  INTEGER NOT NULL REFERENCES usuarios(id),
    dia_semana         SMALLINT,          -- 0=domingo ... 6=sábado
    hora               TIME,
    capacidade_max     INTEGER NOT NULL DEFAULT 14,
    ativo              BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_grupo_regiao CHECK (regiao IN ('OMBRO','JOELHO','COLUNA','OUTRO')),
    CONSTRAINT chk_grupo_dia    CHECK (dia_semana BETWEEN 0 AND 6),
    CONSTRAINT chk_grupo_cap    CHECK (capacidade_max BETWEEN 1 AND 20)
);

-- Composição do grupo. data_saida NULL = ainda participa.
CREATE TABLE grupo_pacientes (
    id           SERIAL PRIMARY KEY,
    grupo_id     INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    paciente_id  INTEGER NOT NULL REFERENCES pacientes(id),
    ciclo_id     INTEGER REFERENCES ciclos_tratamento(id),
    data_entrada DATE NOT NULL DEFAULT CURRENT_DATE,
    data_saida   DATE
);
-- Impede o mesmo paciente ativo duas vezes no mesmo grupo.
CREATE UNIQUE INDEX uq_grupo_paciente_ativo
    ON grupo_pacientes(grupo_id, paciente_id)
    WHERE data_saida IS NULL;

-- ------------------------------------------------------------
-- 5. AGENDAMENTOS
-- Um agendamento é individual (paciente_id) OU de grupo (grupo_id).
-- ------------------------------------------------------------
CREATE TABLE agendamentos (
    id                 SERIAL PRIMARY KEY,
    tipo               VARCHAR(20) NOT NULL,
    paciente_id        INTEGER REFERENCES pacientes(id),
    grupo_id           INTEGER REFERENCES grupos(id),
    ciclo_id           INTEGER REFERENCES ciclos_tratamento(id),
    fisioterapeuta_id  INTEGER NOT NULL REFERENCES usuarios(id),
    data               DATE NOT NULL,
    hora               TIME NOT NULL,
    duracao_min        INTEGER NOT NULL DEFAULT 30,
    numero_sessao      INTEGER,           -- 1..10 dentro do ciclo
    status             VARCHAR(20) NOT NULL DEFAULT 'AGENDADO',
    observacoes        TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_ag_tipo   CHECK (tipo IN ('AVALIACAO','SESSAO','GRUPO')),
    CONSTRAINT chk_ag_status CHECK (status IN ('AGENDADO','CONFIRMADO','REALIZADO','CANCELADO','FALTOU')),
    -- ou é individual, ou é de grupo: nunca os dois, nunca nenhum
    CONSTRAINT chk_ag_alvo CHECK (
        (paciente_id IS NOT NULL AND grupo_id IS NULL)
     OR (paciente_id IS NULL AND grupo_id IS NOT NULL)
    )
);
CREATE INDEX idx_ag_data       ON agendamentos(data);
CREATE INDEX idx_ag_fisio_data ON agendamentos(fisioterapeuta_id, data, hora);
CREATE INDEX idx_ag_ciclo      ON agendamentos(ciclo_id);

-- REGRA: até 2 pacientes por profissional no mesmo horário (individual).
-- Postgres não expressa "no máximo 2" em constraint simples,
-- então a validação fica no Flask, ANTES do insert:
--   SELECT count(*) FROM agendamentos
--    WHERE fisioterapeuta_id = ? AND data = ? AND hora = ?
--      AND tipo <> 'GRUPO' AND status <> 'CANCELADO';
--   -- se >= 2, recusar com mensagem de horário lotado.

-- ------------------------------------------------------------
-- 6. PRESENCAS
-- Serve para individual e para grupo. Numa sessão de grupo,
-- gera-se uma linha por participante.
-- ------------------------------------------------------------
CREATE TABLE presencas (
    id              SERIAL PRIMARY KEY,
    agendamento_id  INTEGER NOT NULL REFERENCES agendamentos(id) ON DELETE CASCADE,
    paciente_id     INTEGER NOT NULL REFERENCES pacientes(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'PRESENTE',
    justificativa   TEXT,
    registrado_por  INTEGER REFERENCES usuarios(id),
    registrado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_presenca_status CHECK (status IN ('PRESENTE','FALTA','FALTA_JUSTIFICADA')),
    CONSTRAINT uq_presenca UNIQUE (agendamento_id, paciente_id)
);
CREATE INDEX idx_presencas_paciente ON presencas(paciente_id);

-- ------------------------------------------------------------
-- 7. EVOLUCOES  (prontuário / evolução clínica)
-- ------------------------------------------------------------
CREATE TABLE evolucoes (
    id                 SERIAL PRIMARY KEY,
    ciclo_id           INTEGER REFERENCES ciclos_tratamento(id),
    paciente_id        INTEGER NOT NULL REFERENCES pacientes(id),
    agendamento_id     INTEGER REFERENCES agendamentos(id),
    fisioterapeuta_id  INTEGER NOT NULL REFERENCES usuarios(id),
    data               DATE NOT NULL,
    descricao          TEXT,
    evolucao           TEXT,
    observacoes        TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evolucoes_paciente ON evolucoes(paciente_id);
CREATE INDEX idx_evolucoes_ciclo    ON evolucoes(ciclo_id);

-- ------------------------------------------------------------
-- 8. FERIADOS  (para o cartão pular datas)
-- Carregar uma vez por ano. Nacionais podem vir da BrasilAPI;
-- municipais e facultativos entram no cadastro manual.
-- ------------------------------------------------------------
CREATE TABLE feriados (
    id     SERIAL PRIMARY KEY,
    data   DATE NOT NULL UNIQUE,
    nome   VARCHAR(150) NOT NULL,
    tipo   VARCHAR(20) NOT NULL DEFAULT 'NACIONAL',
    CONSTRAINT chk_feriado_tipo CHECK (tipo IN ('NACIONAL','ESTADUAL','MUNICIPAL','FACULTATIVO'))
);

-- ------------------------------------------------------------
-- 9. CARTOES  (cartão gerado do ciclo)
-- As datas do cartão são os próprios agendamentos do ciclo.
-- ------------------------------------------------------------
CREATE TABLE cartoes (
    id          SERIAL PRIMARY KEY,
    ciclo_id    INTEGER NOT NULL REFERENCES ciclos_tratamento(id) ON DELETE CASCADE,
    gerado_por  INTEGER REFERENCES usuarios(id),
    gerado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    observacoes TEXT
);

-- ============================================================
-- VIEW de apoio ao relatório mensal (requisito de análise do PI)
-- ============================================================
CREATE VIEW vw_relatorio_mensal AS
SELECT
    date_trunc('month', a.data)::date              AS mes,
    u.nome                                          AS fisioterapeuta,
    a.tipo,
    count(*)                                        AS total_agendamentos,
    count(*) FILTER (WHERE a.status = 'REALIZADO')  AS realizados,
    count(*) FILTER (WHERE a.status = 'FALTOU')     AS faltas,
    count(*) FILTER (WHERE a.status = 'CANCELADO')  AS cancelados
FROM agendamentos a
JOIN usuarios u ON u.id = a.fisioterapeuta_id
GROUP BY 1, 2, 3;
