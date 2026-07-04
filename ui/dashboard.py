"""
ui/dashboard.py — Dashboard principal com visão geral da competição.
"""

from __future__ import annotations

import streamlit as st
from datetime import date, timedelta

from services.round_service import RoundService
from services.ranking_service import RankingService
from repositories.bet_repository import BetRepository
from utils.datetime_utils import (
    get_today_br, format_br_date, format_br_datetime, format_deadline_remaining
)
from utils.formatting import (
    format_currency, format_profit, format_round_status,
    format_bet_status, format_percentage
)
from config.settings import MAX_BETS_PER_DAY


def render_dashboard() -> None:
    """Renderiza o dashboard principal."""

    st.markdown("## 🏠 Dashboard")

    competitor_id = st.session_state.get("competitor_id")
    full_name = st.session_state.get("full_name", "Competidor")
    today = get_today_br()

    # --- Verificação de rodada ---
    RoundService.check_and_auto_close()
    active_round = RoundService.get_active_round()

    # --- Saudação personalizada ---
    hour = __import__("datetime").datetime.now().hour
    greeting = "Bom dia" if hour < 12 else "Boa tarde" if hour < 18 else "Boa noite"
    st.markdown(f"### {greeting}, **{full_name}**! 👋")

    if not active_round:
        st.warning("⚠️ Nenhuma rodada ativa no momento. Aguarde o início da próxima semana.")
        return

    # --- Métricas da rodada ---
    st.markdown(f"**{active_round.label}** — {format_round_status(active_round.status)}")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    # Conta apostas do dia do competidor
    bets_today = 0
    if competitor_id:
        bets_today = BetRepository.count_bets_today(competitor_id, today)

    with col1:
        st.metric(
            label="📅 Apostas Hoje",
            value=f"{bets_today}/{MAX_BETS_PER_DAY}",
            delta=f"{'Disponível' if bets_today < MAX_BETS_PER_DAY else 'Limite atingido'}",
            delta_color="normal" if bets_today < MAX_BETS_PER_DAY else "inverse",
        )

    with col2:
        # Prazo para amanhã
        tomorrow = today + timedelta(days=1)
        deadline_label = format_deadline_remaining(tomorrow)
        st.metric(label="⏰ Prazo p/ Amanhã", value=deadline_label)

    with col3:
        end_date_label = format_br_date(active_round.end_date) if active_round.end_date else "—"
        st.metric(label="📆 Encerra em", value=end_date_label)

    with col4:
        remaining_days = (active_round.end_date - today).days if active_round.end_date else 0
        st.metric(
            label="🗓️ Dias Restantes",
            value=f"{max(0, remaining_days)} dia(s)",
        )

    st.divider()

    # --- Apostas recentes do competidor ---
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### 🎯 Minhas apostas recentes")
        if competitor_id:
            bets = BetRepository.get_bets_by_competitor(competitor_id, limit=5)
            if not bets:
                st.info("Você ainda não registrou nenhuma aposta nesta competição.")
            else:
                for bet in bets:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 1, 1])
                        with c1:
                            st.write(f"📅 {format_br_date(bet.target_date)}")
                            st.caption(format_bet_status(bet.status))
                        with c2:
                            st.write(f"**Odd:** {bet.total_odd:.2f}")
                            st.caption(f"R$ {bet.stake_value:.2f}")
                        with c3:
                            st.write(f"**{bet.combined_count}x**")
                            st.caption("seleção(ões)")
        else:
            st.info("Perfil de competidor não encontrado.")

        if st.button("📋 Ver todas as apostas", key="dash_ver_apostas"):
            st.session_state.current_page = "apostas"
            st.rerun()

    with col_right:
        st.markdown("### 🏆 Ranking da Semana")
        if active_round and active_round.id:
            leaderboard = RankingService.get_leaderboard(active_round.id, limit=5)
            if not leaderboard:
                st.info("Ainda não há apostas liquidadas nesta rodada.")
            else:
                for entry in leaderboard:
                    medal = ["🥇", "🥈", "🥉"].get(entry.position - 1, f"{entry.position}°") \
                        if entry.position <= 3 else f"{entry.position}°"
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 2])
                        with c1:
                            st.write(f"{medal} **{entry.display_name}**")
                            st.caption(f"Taxa de acerto: {entry.win_rate_pct}")
                        with c2:
                            profit_str = format_profit(entry.net_profit)
                            st.write(profit_str)
        else:
            st.info("Ranking disponível após liquidação das apostas.")

        if st.button("📊 Ver ranking completo", key="dash_ver_ranking"):
            st.session_state.current_page = "rodada"
            st.rerun()

    # --- Alerta de prazo próximo ---
    st.divider()
    if not is_deadline_passed_today(today):
        st.success(
            f"✅ **Prazo aberto!** Você pode registrar apostas para hoje ({format_br_date(today)}). "
            f"Prazo: {format_deadline_remaining(today + timedelta(days=1))}"
        )
    else:
        tomorrow = today + timedelta(days=1)
        st.info(
            f"📋 O prazo para hoje expirou. "
            f"Registre apostas para **{format_br_date(tomorrow)}** "
            f"até as 23:59 de hoje."
        )


def is_deadline_passed_today(today: date) -> bool:
    """Verifica se o prazo para apostas de hoje (target_date = amanhã) já passou."""
    from utils.datetime_utils import is_deadline_passed
    return is_deadline_passed(today + timedelta(days=1))
