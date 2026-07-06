"""
ui/admin.py — Painel administrativo completo.
Revisão de apostas, fechamento de rodada, ajuste manual e auditoria.
"""

from __future__ import annotations

from datetime import date

import streamlit as st
import pandas as pd

from services.auth_service import AuthService
from services.round_service import RoundService
from agents.auditoria import AgentAuditoria
from agents.ranking import AgentRanking
from repositories.bet_repository import BetRepository
from repositories.round_repository import RoundRepository
from repositories.audit_repository import AuditRepository
from repositories.competitor_repository import CompetitorRepository
from repositories.settlement_repository import SettlementRepository
from models.bet import Settlement
from models.audit import AuditAction
from utils.datetime_utils import format_br_date, format_br_datetime
from utils.formatting import (
    format_bet_status, format_round_status, format_currency, format_profit
)


def render_admin() -> None:
    """Renderiza o painel administrativo."""
    AuthService.require_admin()

    st.markdown("## ⚙️ Painel Administrativo")

    tab_revisao, tab_rodada, tab_liquidacao, tab_competidores, tab_logs = st.tabs([
        "🔍 Revisão de Apostas",
        "🗓️ Gestão de Rodada",
        "💸 Liquidação",
        "👥 Competidores",
        "📊 Logs de Auditoria",
    ])

    with tab_revisao:
        _render_revisao_apostas()

    with tab_rodada:
        _render_gestao_rodada()

    with tab_liquidacao:
        _render_liquidacao()

    with tab_competidores:
        _render_admin_competidores()

    with tab_logs:
        _render_audit_logs()


def _render_revisao_apostas() -> None:
    """Revisão e aprovação/rejeição manual de apostas."""
    st.markdown("### 🔍 Apostas Pendentes de Revisão")
    actor_id = st.session_state.get("user_id")

    pending = BetRepository.get_pending_review_bets()

    if not pending:
        st.success("✅ Nenhuma aposta pendente de revisão!")
        return

    st.info(f"**{len(pending)} aposta(s)** aguardando revisão.")

    competitors = {c.id: c.display_name for c in CompetitorRepository.get_all_competitors()}

    for bet in pending:
        comp_name = competitors.get(bet.competitor_id, "—")
        with st.expander(
            f"📋 {comp_name} | {format_br_date(bet.target_date)} | "
            f"Odd {bet.total_odd:.2f} | {format_bet_status(bet.status)}",
            expanded=False,
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Competidor:** {comp_name}")
                st.write(f"**Data:** {format_br_date(bet.target_date)}")
                st.write(f"**Odd Total:** {bet.total_odd:.2f}")
                st.write(f"**Stake:** {format_currency(bet.stake_value)}")
            with col2:
                st.write(f"**Combinadas:** {bet.combined_count}")
                conf = f"{bet.ocr_confidence:.0%}" if bet.ocr_confidence else "N/D"
                st.write(f"**Confiança IA:** {conf}")
                st.write(f"**Status:** {format_bet_status(bet.status)}")
                if bet.notes:
                    st.caption(f"📝 {bet.notes}")

            # --- Visualização do Comprovante de Aposta ---
            from repositories.image_repository import ImageRepository
            from config.settings import STORAGE_BUCKET
            
            img_record = ImageRepository.get_image_by_bet(bet.id)
            if img_record:
                try:
                    client = get_admin_client()
                    img_bytes = client.storage.from_(STORAGE_BUCKET).download(img_record.storage_path)
                    st.image(img_bytes, caption=f"Comprovante: {img_record.original_filename}", width=350)
                except Exception as img_err:
                    st.warning(f"Não foi possível carregar a imagem do comprovante: {img_err}")

            # Seleções
            selections = BetRepository.get_selections_by_bet(bet.id)
            if selections:
                st.markdown("**Seleções extraídas:**")
                for sel in selections:
                    st.write(f"  {sel.selection_order}. {sel.description} — Odd {sel.odd:.2f}")

            # Ajuste de Valores Manual (se necessário)
            st.markdown("**Ajuste de Valores Manual (se necessário):**")
            col_adj_stake, col_adj_odd = st.columns(2)
            with col_adj_stake:
                adj_stake = st.number_input(
                    "Ajustar Stake (R$)",
                    min_value=1.0,
                    value=float(bet.stake_value),
                    step=0.5,
                    key=f"adj_stake_{bet.id}"
                )
            with col_adj_odd:
                adj_odd = st.number_input(
                    "Ajustar Odd Total",
                    min_value=1.00,
                    value=float(bet.total_odd),
                    step=0.01,
                    key=f"adj_odd_{bet.id}"
                )

            # Ações
            col_approve, col_reject = st.columns(2)
            notes_key = f"admin_notes_{bet.id}"
            notes = st.text_area("Observações (opcional)", key=notes_key)

            with col_approve:
                if st.button("✅ Aprovar", key=f"approve_{bet.id}", type="primary", use_container_width=True):
                    # Atualiza aposta no banco
                    bet_data = {
                        "status": "approved",
                        "stake_value": adj_stake,
                        "total_odd": adj_odd,
                    }
                    if notes:
                        bet_data["notes"] = notes
                    
                    BetRepository.update_bet(bet.id, bet_data)
                    AgentAuditoria.log_manual_adjustment(
                        actor_id, bet.id, bet.status, "approved", notes or f"Aprovado pelo admin (Stake: R$ {adj_stake:.2f}, Odd: {adj_odd:.2f})"
                    )
                    st.success("Aposta aprovada com sucesso!")
                    st.rerun()

            with col_reject:
                if st.button("❌ Rejeitar", key=f"reject_{bet.id}", use_container_width=True):
                    old_status = bet.status
                    BetRepository.update_bet_status(bet.id, "rejected", notes)
                    AgentAuditoria.log_manual_adjustment(
                        actor_id, bet.id, old_status, "rejected", notes or "Rejeitado pelo admin"
                    )
                    st.warning("Aposta rejeitada.")
                    st.rerun()


def _render_gestao_rodada() -> None:
    """Fechamento e finalização de rodadas."""
    st.markdown("### 🗓️ Gestão de Rodada")
    actor_id = st.session_state.get("user_id")

    active_round = RoundRepository.get_active_round()

    if active_round:
        st.success(f"**Rodada ativa:** {active_round.label}")
        st.write(f"Status: {format_round_status(active_round.status)}")

        col1, col2 = st.columns(2)
        with col1:
            if active_round.status == "open":
                if st.button("🔴 Fechar Rodada", type="primary", use_container_width=True):
                    with st.spinner("Fechando rodada..."):
                        RoundService.close_round(active_round.id)
                        AgentAuditoria.log_round_closed(actor_id, active_round.id)
                        st.success("Rodada fechada!")
                        st.rerun()

        with col2:
            if active_round.status == "closed":
                if st.button("🏆 Finalizar e Calcular Vencedor", type="primary", use_container_width=True):
                    with st.spinner("Calculando vencedor..."):
                        agent_ranking = AgentRanking()
                        winner_id = agent_ranking.determine_winner(active_round.id, actor_id)
                        RoundService.finalize_round(active_round.id)
                        AgentAuditoria.log_round_finalized(actor_id, active_round.id, winner_id)

                        if winner_id:
                            winner = CompetitorRepository.get_competitor_by_id(winner_id)
                            st.success(f"🏆 Vencedor: **{winner.display_name if winner else winner_id}**!")
                        else:
                            st.warning("Nenhum vencedor determinado (sem apostas liquidadas).")
                        st.rerun()
    else:
        st.warning("Nenhuma rodada ativa no momento.")
        if st.button("🟢 Criar Nova Rodada", type="primary"):
            RoundService.ensure_active_round()
            st.success("Nova rodada criada!")
            st.rerun()

    # Histórico
    st.divider()
    st.markdown("**Histórico de Rodadas**")
    rounds = RoundRepository.get_all_rounds(limit=10)
    if rounds:
        for r in rounds:
            winner_info = ""
            if r.winner_competitor_id:
                winner = CompetitorRepository.get_competitor_by_id(r.winner_competitor_id)
                winner_info = f" — 🏆 {winner.display_name}" if winner else ""
            st.write(f"- {r.label} | {format_round_status(r.status)}{winner_info}")


def _render_liquidacao() -> None:
    """Liquidação automática e manual de apostas."""
    st.markdown("### 💸 Liquidação de Apostas")
    actor_id = st.session_state.get("user_id")

    # --- Seção do Liquidador Automático ---
    st.markdown("#### 🤖 Resolvedor Automático por IA")
    st.write(
        "Esta ferramenta consulta os resultados reais dos jogos na web em tempo real "
        "usando inteligência artificial (Gemini + Google Search) e resolve as seleções e apostas pendentes."
    )
    
    if st.button("🤖 Executar Liquidador Automático", type="secondary", use_container_width=True):
        with st.spinner("Conferindo jogos e liquidando apostas com a IA..."):
            try:
                from services.settlement_service import SettlementService
                results = SettlementService.run_auto_settlement()
                
                # Apresenta resultados
                st.success(
                    f"✅ Concluído! "
                    f"Seleções analisadas: {results['selections_checked']} | "
                    f"Seleções resolvidas: {results['selections_resolved']} | "
                    f"Apostas liquidadas: {results['bets_settled']}"
                )

                # Verifica se houve estouro de cota nos logs detalhados
                quota_error = any("429" in str(log_msg) or "RESOURCE_EXHAUSTED" in str(log_msg) for log_msg in results["logs"])
                if quota_error and results["selections_resolved"] == 0:
                    st.warning(
                        "⚠️ **Limite de Cota do Gemini Atingido:** A sua chave de API gratuita do Gemini "
                        "excedeu o limite total de uso diário ou mensal permitido pelo Google AI Studio.\n\n"
                        "**Como resolver:**\n"
                        "1. Acesse o [Google AI Studio](https://aistudio.google.dev/) e ative o faturamento (Billing) para migrar ao plano Pay-as-you-go (que possui limites muito maiores e uso gratuito generoso sem cobranças se mantido no uso padrão).\n"
                        "2. Ou gere uma nova chave de API gratuita em outra conta do Google e a atualize no seu arquivo `.env`.\n"
                        "3. Enquanto isso, você pode **liquidar manualmente** as apostas da rodada atual utilizando o painel abaixo!"
                    )
                
                with st.expander("Ver logs detalhados do resolvedor", expanded=True):
                    for log_msg in results["logs"]:
                        st.write(log_msg)
            except Exception as ex:
                st.error(f"❌ Erro ao executar o resolvedor: {ex}")
                
    st.divider()

    active_round = RoundRepository.get_active_round()
    if not active_round:
        st.warning("Nenhuma rodada ativa.")
        return

    approved_bets = [
        b for b in BetRepository.get_bets_by_round(active_round.id)
        if b.status == "approved"
    ]

    if not approved_bets:
        st.info("Nenhuma aposta aprovada aguardando liquidação.")
        return

    competitors = {c.id: c.display_name for c in CompetitorRepository.get_all_competitors()}

    st.info(f"**{len(approved_bets)}** aposta(s) aguardando liquidação.")

    for bet in approved_bets:
        comp_name = competitors.get(bet.competitor_id, "—")
        with st.expander(f"💰 {comp_name} | {format_br_date(bet.target_date)} | Odd {bet.total_odd:.2f}"):
            st.write(f"**Stake:** {format_currency(bet.stake_value)}")
            gross_return = bet.stake_value * bet.total_odd
            st.write(f"**Retorno potencial (se ganhar):** {format_currency(gross_return)}")

            outcome = st.radio(
                "Resultado:",
                options=["win", "loss", "void"],
                format_func=lambda x: {"win": "🏆 Ganhou", "loss": "💸 Perdeu", "void": "↩️ Anulada"}[x],
                horizontal=True,
                key=f"outcome_{bet.id}",
            )

            if st.button("💾 Liquidar", key=f"settle_{bet.id}", type="primary", use_container_width=True):
                with st.spinner("Liquidando..."):
                    net_profit = (gross_return - bet.stake_value) if outcome == "win" else \
                                 (-bet.stake_value) if outcome == "loss" else 0.0

                    settlement = Settlement(
                        bet_id=bet.id,
                        outcome=outcome,
                        gross_return=gross_return if outcome == "win" else None,
                        net_profit=net_profit,
                    )
                    SettlementRepository.upsert_settlement(settlement)
                    BetRepository.update_bet_status(bet.id, "settled")
                    AgentAuditoria.log(
                        AuditAction.BET_APPROVED,
                        actor_id=actor_id,
                        entity_name="settlements",
                        entity_id=bet.id,
                        payload={"outcome": outcome, "net_profit": net_profit},
                    )
                    st.success(f"Aposta liquidada: {format_profit(net_profit)}")
                    st.rerun()


def _render_admin_competidores() -> None:
    """Cadastro de novos competidores."""
    st.markdown("### 👥 Cadastro de Competidores")

    if "competitor_created_success" in st.session_state:
        st.success(st.session_state["competitor_created_success"])
        del st.session_state["competitor_created_success"]

    with st.form("cadastro_competidor", clear_on_submit=True):
        full_name = st.text_input("Nome completo")
        display_name = st.text_input("Nome de exibição")
        st.caption("O competidor será cadastrado localmente no banco para ranking e controle de apostas.")

        submitted = st.form_submit_button("Cadastrar Competidor", type="primary")

        if submitted and full_name:
            import uuid
            from models.competitor import Profile, Competitor
            
            final_display = display_name or full_name
            fake_email = f"competidor_{uuid.uuid4().hex[:8]}@n1.local"
            
            try:
                from config.supabase_client import get_admin_client
                admin_client = get_admin_client()
                
                # 1. Cria usuário silencioso no Supabase Auth para satisfazer FK
                auth_res = admin_client.auth.admin.create_user({
                    "email": fake_email,
                    "password": uuid.uuid4().hex,
                    "email_confirm": True
                })
                
                if not auth_res or not auth_res.user:
                    raise Exception("Falha ao criar credenciais no Supabase Auth.")
                
                auth_user_id = auth_res.user.id

                # 2. Cria perfil vinculado ao auth_user_id
                profile = Profile(
                    auth_user_id=auth_user_id,
                    full_name=full_name,
                    email=fake_email,
                    role="competidor",
                )
                profile = CompetitorRepository.create_profile(profile)

                # 3. Cria competidor
                competitor = Competitor(
                    profile_id=profile.id,
                    display_name=final_display,
                )
                competitor = CompetitorRepository.create_competitor(competitor)
                
                # Log de auditoria
                AgentAuditoria.log(
                    "COMPETITOR_CREATED",
                    entity_name="competitors",
                    entity_id=competitor.id,
                    payload={"display_name": competitor.display_name, "email": fake_email},
                )
                
                st.session_state["competitor_created_success"] = f"✅ Competidor '{final_display}' cadastrado com sucesso!"
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao cadastrar competidor: {e}")


def _render_audit_logs() -> None:
    """Exibe logs de auditoria filtráveis."""
    st.markdown("### 📊 Logs de Auditoria")

    col1, col2 = st.columns(2)
    with col1:
        action_filter = st.selectbox(
            "Filtrar por ação",
            options=["Todas", "LOGIN", "BET_SUBMITTED", "BET_REJECTED",
                     "ROUND_CLOSED", "WINNER_DEFINED", "BET_MANUAL_ADJUST",
                     "UPLOAD_BLOCKED", "LIMIT_EXCEEDED", "DEADLINE_EXCEEDED"],
            key="audit_action_filter",
        )
    with col2:
        limit = st.number_input("Limite de registros", min_value=10, max_value=500, value=100)

    if action_filter == "Todas":
        logs = AuditRepository.get_recent_logs(limit=int(limit))
    else:
        logs = AuditRepository.get_logs_by_action(action_filter, limit=int(limit))

    if not logs:
        st.info("Nenhum log encontrado.")
        return

    st.markdown(f"**{len(logs)} registro(s)**")

    logs_data = []
    for log in logs:
        logs_data.append({
            "Data/Hora": format_br_datetime(log.created_at) if log.created_at else "—",
            "Ação": log.action,
            "Entidade": log.entity_name or "—",
            "ID Entidade": (log.entity_id[:8] + "...") if log.entity_id and len(log.entity_id) > 8 else (log.entity_id or "—"),
            "Actor": (str(log.actor_id)[:8] + "...") if log.actor_id else "Sistema",
        })

    df = pd.DataFrame(logs_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
