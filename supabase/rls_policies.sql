-- ============================================================
-- Web App Controle de Apostas N1 — Políticas RLS
-- Row Level Security para todas as tabelas críticas
-- ============================================================

-- Habilitar RLS em todas as tabelas
ALTER TABLE public.profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.competitors     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.competitions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rounds          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bets            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bet_selections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bet_images      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settlements     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs      ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Funções auxiliares de autorização
-- ============================================================

-- Retorna o role do usuário autenticado atual
CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS TEXT AS $$
    SELECT role
    FROM public.profiles
    WHERE auth_user_id = auth.uid()
    LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Retorna o profile_id do usuário autenticado atual
CREATE OR REPLACE FUNCTION public.get_current_profile_id()
RETURNS UUID AS $$
    SELECT id
    FROM public.profiles
    WHERE auth_user_id = auth.uid()
    LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Retorna o competitor_id do usuário autenticado atual
CREATE OR REPLACE FUNCTION public.get_current_competitor_id()
RETURNS UUID AS $$
    SELECT c.id
    FROM public.competitors c
    JOIN public.profiles p ON p.id = c.profile_id
    WHERE p.auth_user_id = auth.uid()
    LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Verifica se o usuário atual é admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE auth_user_id = auth.uid()
          AND role = 'admin'
    );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ============================================================
-- profiles — Políticas
-- ============================================================
-- Competidor: vê apenas o próprio perfil
CREATE POLICY profiles_select_own ON public.profiles
    FOR SELECT
    USING (auth_user_id = auth.uid() OR public.is_admin());

-- Competidor: atualiza apenas o próprio perfil
CREATE POLICY profiles_update_own ON public.profiles
    FOR UPDATE
    USING (auth_user_id = auth.uid() OR public.is_admin());

-- Somente o sistema (service role) insere profiles via trigger
CREATE POLICY profiles_insert_system ON public.profiles
    FOR INSERT
    WITH CHECK (auth_user_id = auth.uid() OR public.is_admin());

-- ============================================================
-- competitors — Políticas
-- ============================================================
-- Todos os autenticados podem ver (lista de competidores)
CREATE POLICY competitors_select_all ON public.competitors
    FOR SELECT
    USING (auth.role() = 'authenticated');

-- Somente admin insere/atualiza/deleta competitors
CREATE POLICY competitors_manage_admin ON public.competitors
    FOR ALL
    USING (public.is_admin());

-- ============================================================
-- competitions — Políticas
-- ============================================================
-- Todos os autenticados podem ver
CREATE POLICY competitions_select_all ON public.competitions
    FOR SELECT
    USING (auth.role() = 'authenticated');

-- Somente admin modifica
CREATE POLICY competitions_manage_admin ON public.competitions
    FOR ALL
    USING (public.is_admin());

-- ============================================================
-- rounds — Políticas
-- ============================================================
-- Todos os autenticados podem ver
CREATE POLICY rounds_select_all ON public.rounds
    FOR SELECT
    USING (auth.role() = 'authenticated');

-- Somente admin insere/atualiza/deleta
CREATE POLICY rounds_manage_admin ON public.rounds
    FOR ALL
    USING (public.is_admin());

-- ============================================================
-- bets — Políticas
-- ============================================================
-- Competidor: vê somente suas próprias apostas
CREATE POLICY bets_select_own ON public.bets
    FOR SELECT
    USING (
        competitor_id = public.get_current_competitor_id()
        OR public.is_admin()
    );

-- Competidor: insere somente suas próprias apostas
CREATE POLICY bets_insert_own ON public.bets
    FOR INSERT
    WITH CHECK (
        competitor_id = public.get_current_competitor_id()
    );

-- Competidor: atualiza somente suas apostas em rascunho (draft)
CREATE POLICY bets_update_draft ON public.bets
    FOR UPDATE
    USING (
        (competitor_id = public.get_current_competitor_id() AND status = 'draft')
        OR public.is_admin()
    );

-- Admin pode deletar (apenas admin)
CREATE POLICY bets_delete_admin ON public.bets
    FOR DELETE
    USING (public.is_admin());

-- ============================================================
-- bet_selections — Políticas
-- ============================================================
CREATE POLICY bet_selections_select ON public.bet_selections
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.bets b
            WHERE b.id = bet_id
              AND (
                  b.competitor_id = public.get_current_competitor_id()
                  OR public.is_admin()
              )
        )
    );

CREATE POLICY bet_selections_insert ON public.bet_selections
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.bets b
            WHERE b.id = bet_id
              AND b.competitor_id = public.get_current_competitor_id()
        )
    );

CREATE POLICY bet_selections_manage_admin ON public.bet_selections
    FOR ALL
    USING (public.is_admin());

-- ============================================================
-- bet_images — Políticas
-- ============================================================
CREATE POLICY bet_images_select_own ON public.bet_images
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.bets b
            WHERE b.id = bet_id
              AND (
                  b.competitor_id = public.get_current_competitor_id()
                  OR public.is_admin()
              )
        )
    );

CREATE POLICY bet_images_insert_own ON public.bet_images
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.bets b
            WHERE b.id = bet_id
              AND b.competitor_id = public.get_current_competitor_id()
        )
    );

CREATE POLICY bet_images_manage_admin ON public.bet_images
    FOR ALL
    USING (public.is_admin());

-- ============================================================
-- settlements — Políticas
-- ============================================================
CREATE POLICY settlements_select ON public.settlements
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.bets b
            WHERE b.id = bet_id
              AND (
                  b.competitor_id = public.get_current_competitor_id()
                  OR public.is_admin()
              )
        )
    );

-- Somente admin (ou service role) insere/atualiza liquidações
CREATE POLICY settlements_manage_admin ON public.settlements
    FOR ALL
    USING (public.is_admin());

-- ============================================================
-- audit_logs — Políticas
-- ============================================================
-- Somente admin lê os logs
CREATE POLICY audit_logs_select_admin ON public.audit_logs
    FOR SELECT
    USING (public.is_admin());

-- Qualquer usuário autenticado pode inserir (o sistema insere via service role)
-- Inserção controlada pela service_role_key no backend
CREATE POLICY audit_logs_insert_system ON public.audit_logs
    FOR INSERT
    WITH CHECK (TRUE);

-- ============================================================
-- Storage: Bucket "bet-images" — Políticas
-- Execute após criar o bucket no Supabase Dashboard
-- ============================================================

-- Criar bucket privado (execute no Supabase SQL Editor ou Dashboard)
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('bet-images', 'bet-images', false)
-- ON CONFLICT DO NOTHING;

-- Competidor: acessa apenas seus próprios arquivos
-- Path esperado: bet-images/{competitor_id}/{bet_id}/{filename}
CREATE POLICY storage_select_own ON storage.objects
    FOR SELECT
    USING (
        bucket_id = 'bet-images'
        AND (
            (storage.foldername(name))[1] = public.get_current_competitor_id()::TEXT
            OR public.is_admin()
        )
    );

CREATE POLICY storage_insert_own ON storage.objects
    FOR INSERT
    WITH CHECK (
        bucket_id = 'bet-images'
        AND (storage.foldername(name))[1] = public.get_current_competitor_id()::TEXT
    );

CREATE POLICY storage_manage_admin ON storage.objects
    FOR ALL
    USING (
        bucket_id = 'bet-images'
        AND public.is_admin()
    );
