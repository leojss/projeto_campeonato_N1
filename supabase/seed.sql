-- ============================================================
-- Web App Controle de Apostas N1 — Dados Iniciais (Seed)
-- Execute APÓS o schema.sql
-- ============================================================

-- ATENÇÃO: Este script usa INSERT ... ON CONFLICT DO NOTHING
-- para ser idempotente (seguro para reexecutar).

-- ============================================================
-- 1. Criação do usuário Admin via Supabase Auth
-- IMPORTANTE: Crie o usuário admin manualmente no Supabase
-- Dashboard (Authentication > Users) e copie o UUID gerado.
-- Em seguida substitua o valor abaixo pelo UUID real.
-- ============================================================
-- Exemplo de UUID do admin (substitua pelo real):
-- DO $$
-- DECLARE
--     v_admin_auth_id UUID := 'SEU-UUID-DO-ADMIN-AQUI';
-- BEGIN
--     INSERT INTO public.profiles (auth_user_id, full_name, email, role)
--     VALUES (v_admin_auth_id, 'Administrador', 'admin@apostasn1.com', 'admin')
--     ON CONFLICT (auth_user_id) DO NOTHING;
-- END $$;

-- ============================================================
-- 2. Competição inicial
-- ============================================================
INSERT INTO public.competitions (id, name, description, status, timezone)
VALUES (
    'c0000000-0000-0000-0000-000000000001',
    'Competição N1 — Temporada 2026',
    'Competição interna de apostas — Temporada 2026. Uma rodada por semana.',
    'active',
    'America/Sao_Paulo'
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 3. Rodada da semana atual
-- A função calcula o domingo e sábado da semana corrente
-- ============================================================
DO $$
DECLARE
    v_today         DATE := CURRENT_DATE AT TIME ZONE 'America/Sao_Paulo';
    v_sunday        DATE;
    v_saturday      DATE;
    v_week_number   INTEGER;
BEGIN
    -- Calcula o domingo da semana atual (DOW: domingo = 0)
    v_sunday    := v_today - EXTRACT(DOW FROM v_today)::INTEGER;
    v_saturday  := v_sunday + 6;
    v_week_number := EXTRACT(WEEK FROM v_sunday)::INTEGER;

    INSERT INTO public.rounds (
        id,
        competition_id,
        week_number,
        start_date,
        end_date,
        status
    )
    VALUES (
        gen_random_uuid(),
        'c0000000-0000-0000-0000-000000000001',
        v_week_number,
        v_sunday,
        v_saturday,
        'open'
    )
    ON CONFLICT (competition_id, week_number) DO NOTHING;
END $$;

-- ============================================================
-- Verificação do seed
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '--- Seed verificado ---';
    RAISE NOTICE 'Competições ativas: %', (SELECT COUNT(*) FROM public.competitions WHERE status = 'active');
    RAISE NOTICE 'Rodadas abertas: %',    (SELECT COUNT(*) FROM public.rounds WHERE status = 'open');
END $$;
