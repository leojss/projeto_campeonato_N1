-- ============================================================
-- Web App Controle de Apostas N1 — Schema do Banco de Dados
-- Supabase Postgres
-- Fuso horário oficial: America/Sao_Paulo
-- ============================================================

-- Extensão para UUID gerado no banco
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Garante que o timezone da sessão está correto
SET timezone = 'America/Sao_Paulo';

-- ============================================================
-- 1. profiles
-- Perfil do usuário vinculado ao Supabase Auth
-- ============================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id    UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'competidor'
                        CHECK (role IN ('competidor', 'admin')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.profiles IS 'Perfis de usuário vinculados ao Supabase Auth';
COMMENT ON COLUMN public.profiles.role IS 'competidor | admin';

-- ============================================================
-- 2. competitors
-- Cadastro lógico do competidor (separado do perfil de auth)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.competitors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID UNIQUE NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    display_name    TEXT NOT NULL,
    avatar_url      TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.competitors IS 'Cadastro lógico dos competidores';

-- ============================================================
-- 3. competitions
-- Competição ativa (uma por vez)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.competitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'paused', 'finished')),
    timezone        TEXT NOT NULL DEFAULT 'America/Sao_Paulo',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.competitions IS 'Competições (uma ativa por vez)';

-- ============================================================
-- 4. rounds
-- Rodadas semanais: domingo 00:00:00 → sábado 23:59:59
-- ============================================================
CREATE TABLE IF NOT EXISTS public.rounds (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id          UUID NOT NULL REFERENCES public.competitions(id) ON DELETE CASCADE,
    week_number             INTEGER NOT NULL,
    start_date              DATE NOT NULL,   -- domingo
    end_date                DATE NOT NULL,   -- sábado
    status                  TEXT NOT NULL DEFAULT 'scheduled'
                                CHECK (status IN ('scheduled', 'open', 'closed', 'finalized')),
    winner_competitor_id    UUID REFERENCES public.competitors(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at               TIMESTAMPTZ,

    CONSTRAINT rounds_date_order CHECK (end_date >= start_date),
    CONSTRAINT rounds_unique_week UNIQUE (competition_id, week_number)
);

COMMENT ON TABLE public.rounds IS 'Rodadas semanais de domingo a sábado';

-- ============================================================
-- 5. bets
-- Apostas submetidas pelos competidores
-- ============================================================
CREATE TABLE IF NOT EXISTS public.bets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id   UUID NOT NULL REFERENCES public.competitors(id),
    round_id        UUID NOT NULL REFERENCES public.rounds(id),
    target_date     DATE NOT NULL,
    submitted_at    TIMESTAMPTZ,
    stake_value     NUMERIC(12, 2) NOT NULL
                        CHECK (stake_value > 0),
    total_odd       NUMERIC(10, 4) NOT NULL
                        CHECK (total_odd >= 1.50),
    combined_count  INTEGER NOT NULL DEFAULT 1
                        CHECK (combined_count BETWEEN 1 AND 3),
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'submitted', 'processing',
                            'approved', 'rejected', 'locked', 'settled', 'review'
                        )),
    deadline_at     TIMESTAMPTZ NOT NULL,
    ocr_confidence  NUMERIC(5, 4),           -- 0.0000 a 1.0000
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.bets IS 'Apostas dos competidores';
COMMENT ON COLUMN public.bets.deadline_at IS 'Prazo máximo: target_date - 1 dia às 23:59:59';
COMMENT ON COLUMN public.bets.total_odd IS 'Produto das odds das seleções (mín 1.50)';
COMMENT ON COLUMN public.bets.combined_count IS 'Número de seleções (máx 3)';

-- Índices para queries mais comuns
CREATE INDEX IF NOT EXISTS idx_bets_competitor_date ON public.bets(competitor_id, target_date);
CREATE INDEX IF NOT EXISTS idx_bets_round ON public.bets(round_id);
CREATE INDEX IF NOT EXISTS idx_bets_status ON public.bets(status);

-- ============================================================
-- 6. bet_selections
-- Seleções individuais de cada aposta (máx 3)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.bet_selections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bet_id              UUID NOT NULL REFERENCES public.bets(id) ON DELETE CASCADE,
    selection_order     INTEGER NOT NULL CHECK (selection_order BETWEEN 1 AND 3),
    description         TEXT NOT NULL,
    odd                 NUMERIC(10, 4) NOT NULL CHECK (odd >= 1.00),
    event_name          TEXT,
    event_datetime      TIMESTAMPTZ,
    result_status       TEXT CHECK (result_status IN ('pending', 'won', 'lost', 'void', 'push')),
    api_fixture_id      TEXT,
    resolved_at         TIMESTAMPTZ,
    resolution_source   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT bet_selections_unique_order UNIQUE (bet_id, selection_order)
);

COMMENT ON TABLE public.bet_selections IS 'Seleções individuais de cada aposta';

-- ============================================================
-- 7. bet_images
-- Imagens enviadas e resultado da leitura por IA
-- ============================================================
CREATE TABLE IF NOT EXISTS public.bet_images (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bet_id              UUID NOT NULL REFERENCES public.bets(id) ON DELETE CASCADE,
    storage_path        TEXT NOT NULL,
    original_filename   TEXT NOT NULL,
    mime_type           TEXT NOT NULL,
    file_size           BIGINT NOT NULL CHECK (file_size > 0),
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    ocr_text            TEXT,
    ocr_json            JSONB,
    confidence_score    NUMERIC(5, 4),
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN (
                                'pending', 'processing', 'extracted',
                                'failed', 'approved', 'rejected'
                            ))
);

COMMENT ON TABLE public.bet_images IS 'Arquivos de imagem das apostas e resultado OCR';

CREATE INDEX IF NOT EXISTS idx_bet_images_bet ON public.bet_images(bet_id);
CREATE INDEX IF NOT EXISTS idx_bet_images_status ON public.bet_images(status);

-- ============================================================
-- 8. settlements
-- Liquidação e fechamento de cada aposta
-- ============================================================
CREATE TABLE IF NOT EXISTS public.settlements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bet_id          UUID UNIQUE NOT NULL REFERENCES public.bets(id) ON DELETE CASCADE,
    settled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome         TEXT NOT NULL CHECK (outcome IN ('win', 'loss', 'void')),
    gross_return    NUMERIC(12, 2),   -- stake × total_odd (se ganhou)
    net_profit      NUMERIC(12, 2),   -- gross_return - stake | -stake se perdeu
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.settlements IS 'Liquidação das apostas';

-- ============================================================
-- 9. audit_logs
-- Auditoria de todas as ações críticas do sistema
-- ============================================================
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        UUID,             -- auth_user_id ou NULL (sistema)
    action          TEXT NOT NULL,    -- LOGIN, UPLOAD, BET_SUBMITTED, etc.
    entity_name     TEXT,             -- nome da tabela/entidade afetada
    entity_id       TEXT,             -- UUID ou outro identificador
    payload         JSONB,            -- dados relevantes da ação
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.audit_logs IS 'Log de auditoria de todas as ações críticas';

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON public.audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON public.audit_logs(created_at DESC);

-- ============================================================
-- Triggers: updated_at automático
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE OR REPLACE TRIGGER trg_bets_updated_at
    BEFORE UPDATE ON public.bets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- Função auxiliar: contar apostas do dia por competidor
-- Usada como guard nas RLS e nos serviços
-- ============================================================
CREATE OR REPLACE FUNCTION public.count_bets_today(p_competitor_id UUID, p_date DATE)
RETURNS INTEGER AS $$
    SELECT COUNT(*)::INTEGER
    FROM public.bets
    WHERE competitor_id = p_competitor_id
      AND target_date = p_date
      AND status NOT IN ('rejected', 'draft');
$$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION public.count_bets_today IS
    'Retorna o número de apostas válidas de um competidor em determinado dia';
