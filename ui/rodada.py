"""
ui/rodada.py — Tela de andamento da rodada atual e ranking completo.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from services.auth_service import AuthService
from services.round_service import RoundService
from services.ranking_service import RankingService
from repositories.bet_repository import BetRepository
from utils.datetime_utils import format_br_date, format_br_datetime
from utils.formatting import (
    format_currency, format_profit, format_round_status,
    format_bet_status, format_percentage,
)


def render_rodada() -> None:
    """Renderiza a tela da rodada atual com ranking completo."""
    AuthService.require_authenticated()

    st.markdown("## 🗓️ Rodada Atual")

    RoundService.check_and_auto_close()
    active_round = RoundService.get_active_round()

    if not active_round:
        st.warning("⚠️ Nenhuma rodada ativa no momento.")

        # Histórico de rodadas encerradas
        from repositories.round_repository import RoundRepository
        all_rounds = RoundRepository.get_all_rounds()
        if all_rounds:
            st.markdown("### 📚 Rodadas Anteriores")
            for r in all_rounds:
                st.write(f"- {r.label} — {format_round_status(r.status)}")
        return

    # --- Informações da rodada ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📅 Início", format_br_date(active_round.start_date))
    with col2:
        st.metric("📅 Encerramento", format_br_date(active_round.end_date))
    with col3:
        st.metric("Status", format_round_status(active_round.status))

    st.divider()

    # --- Ranking da semana ---
    st.markdown("### 🏆 Ranking da Semana")
    ranking = RankingService.compute_weekly_ranking(active_round.id)

    if not ranking:
        st.info("O ranking será exibido após a liquidação das apostas.")
    else:
        ranking_data = []
        for entry in ranking:
            medal = ["🥇", "🥈", "🥉"][entry.position - 1] if entry.position <= 3 else f"{entry.position}°"
            ranking_data.append({
                "Pos.": medal,
                "Competidor": entry.display_name,
                "Apostas": entry.total_bets,
                "Ganhas": entry.winning_bets,
                "Taxa de Acerto": entry.win_rate_pct,
                "Lucro Líquido": format_profit(entry.net_profit),
            })

        df = pd.DataFrame(ranking_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Apostas da semana ---
    st.markdown("### 📋 Apostas da Semana")

    bets = BetRepository.get_bets_by_round(active_round.id)
    if not bets:
        st.info("Nenhuma aposta registrada nesta rodada ainda.")
        return

    # Agrupa por competidor para exibição
    from repositories.competitor_repository import CompetitorRepository
    competitors = {c.id: c.display_name for c in CompetitorRepository.get_all_competitors()}

    bets_data = []
    for bet in bets:
        bets_data.append({
            "Competidor": competitors.get(bet.competitor_id, "—"),
            "Data": format_br_date(bet.target_date),
            "Odd": f"{bet.total_odd:.2f}",
            "Stake": format_currency(bet.stake_value),
            "Seleções": bet.combined_count,
            "Status": format_bet_status(bet.status),
            "Conf. IA": f"{bet.ocr_confidence:.0%}" if bet.ocr_confidence else "—",
        })

    df_bets = pd.DataFrame(bets_data)
    st.dataframe(df_bets, use_container_width=True, hide_index=True)
