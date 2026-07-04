"""
ui/competidores.py — Tela de Ranking Geral e Classificação dos Competidores.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import textwrap

from services.auth_service import AuthService
from repositories.competitor_repository import CompetitorRepository
from repositories.bet_repository import BetRepository
from services.round_service import RoundService
from config.supabase_client import get_admin_client


def render_competidores() -> None:
    """Renderiza a tela de Ranking Geral com Pódio e Classificação."""
    AuthService.require_authenticated()

    # Hero Banner futurista
    try:
        st.image("assets/images/banner.png", width="stretch")
    except Exception:
        pass

    st.markdown("## 📊 Ranking Geral")

    # 1. Busca todos os competidores
    competitors = CompetitorRepository.get_all_competitors()
    if not competitors:
        st.info("📭 Nenhum competidor cadastrado nesta competição.")
        return

    # 2. Busca quantidade de acertos (apostas com outcome = 'win') via Supabase
    win_counts = {}
    try:
        client = get_admin_client()
        result_wins = (
            client.table("settlements")
            .select("outcome, bets(competitor_id)")
            .eq("outcome", "win")
            .execute()
        )
        if result_wins.data:
            for row in result_wins.data:
                bet_info = row.get("bets")
                if bet_info:
                    comp_id = bet_info.get("competitor_id")
                    win_counts[comp_id] = win_counts.get(comp_id, 0) + 1
    except Exception as e:
        st.caption(f"Aviso ao calcular acertos: {e}")

    # Enriquece os competidores com seus acertos
    for c in competitors:
        c.winning_bets = win_counts.get(c.id, 0)

    # 3. Ordena os competidores: 1º por acertos decrescente, 2º por saldo de pontos decrescente
    competitors.sort(key=lambda x: (x.winning_bets, x.points), reverse=True)

    # 4. Renderização do CSS e HTML do Pódio Esportivo
    st.markdown(
        """
        <style>
        .podium-box {
            display: flex;
            justify-content: center;
            align-items: flex-end;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 2.5rem 1rem 1.2rem 1rem;
            gap: 1.2rem;
            margin-bottom: 2rem;
            box-shadow: 0 15px 30px rgba(0,0,0,0.4);
        }
        .podium-place {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 30%;
            text-align: center;
        }
        .podium-avatar {
            font-size: 2.5rem;
            margin-bottom: 0.2rem;
        }
        .podium-name {
            font-weight: 700;
            color: #ffffff;
            font-size: 0.95rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            width: 100%;
        }
        .podium-score {
            font-size: 0.85rem;
            color: #fbbf24;
            margin-bottom: 0.2rem;
            font-weight: 700;
        }
        .podium-score-points {
            color: #818cf8;
            font-size: 0.75rem;
            margin-bottom: 0.6rem;
            font-weight: 600;
        }
        .podium-bar {
            width: 100%;
            border-radius: 8px 8px 0 0;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #ffffff;
            font-weight: 800;
            font-size: 1.4rem;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
            box-shadow: 0 4px 15px rgba(0,0,0,0.25);
            transition: transform 0.2s ease-in-out;
        }
        .podium-bar:hover {
            transform: translateY(-5px);
        }
        .bar-gold {
            height: 110px;
            background: linear-gradient(135deg, #fbbf24, #d97706);
            border: 1px solid #f59e0b;
        }
        .bar-silver {
            height: 80px;
            background: linear-gradient(135deg, #cbd5e1, #64748b);
            border: 1px solid #94a3b8;
        }
        .bar-bronze {
            height: 55px;
            background: linear-gradient(135deg, #d97706, #78350f);
            border: 1px solid #b45309;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Resolve os dados de 1º, 2º e 3º lugares para preencher o HTML
    p1_name, p1_score, p1_pts = "—", "0 acertos", "100.00 pts"
    p2_name, p2_score, p2_pts = "—", "0 acertos", "100.00 pts"
    p3_name, p3_score, p3_pts = "—", "0 acertos", "100.00 pts"

    if len(competitors) >= 1:
        p1_name = competitors[0].display_name
        p1_score = f"🎯 {competitors[0].winning_bets} acertos"
        p1_pts = f"🪙 R$ {competitors[0].points:.2f}"
    if len(competitors) >= 2:
        p2_name = competitors[1].display_name
        p2_score = f"🎯 {competitors[1].winning_bets} acertos"
        p2_pts = f"🪙 R$ {competitors[1].points:.2f}"
    if len(competitors) >= 3:
        p3_name = competitors[2].display_name
        p3_score = f"🎯 {competitors[2].winning_bets} acertos"
        p3_pts = f"🪙 R$ {competitors[2].points:.2f}"

    # Injeta a estrutura do Pódio na ordem visual [2º Lugar, 1º Lugar, 3º Lugar]
    podium_html = (
        "<div class='podium-box'>"
        "<div class='podium-place'>"
        "<div class='podium-avatar'>🥈</div>"
        f"<div class='podium-name' title='{p2_name}'>{p2_name}</div>"
        f"<div class='podium-score' style='color: #cbd5e1;'>{p2_score}</div>"
        f"<div class='podium-score-points'>{p2_pts}</div>"
        "<div class='podium-bar bar-silver'>2º</div>"
        "</div>"
        "<div class='podium-place'>"
        "<div class='podium-avatar'>👑</div>"
        f"<div class='podium-name' title='{p1_name}'>{p1_name}</div>"
        f"<div class='podium-score'>{p1_score}</div>"
        f"<div class='podium-score-points'>{p1_pts}</div>"
        "<div class='podium-bar bar-gold'>1º</div>"
        "</div>"
        "<div class='podium-place'>"
        "<div class='podium-avatar'>🥉</div>"
        f"<div class='podium-name' title='{p3_name}'>{p3_name}</div>"
        f"<div class='podium-score' style='color: #f97316;'>{p3_score}</div>"
        f"<div class='podium-score-points'>{p3_pts}</div>"
        "<div class='podium-bar bar-bronze'>3º</div>"
        "</div>"
        "</div>"
    )
    st.markdown(podium_html, unsafe_allow_html=True)

    # 5. Tabela de Classificação Geral
    st.markdown("### 🏆 Classificação Completa")
    
    active_round = RoundService.get_active_round()

    for idx, comp in enumerate(competitors):
        pos = idx + 1
        medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"**{pos}º**"

        with st.container(border=True):
            col_rank, col_info, col_stats, col_action = st.columns([1.5, 4.5, 4, 3])

            with col_rank:
                st.markdown(
                    f"<div style='font-size: 1.4rem; text-align: center; padding-top: 5px;'>{medal}</div>",
                    unsafe_allow_html=True,
                )

            with col_info:
                st.markdown(f"**{comp.display_name}**")
                # Detalhes rápidos da rodada atual
                if active_round and comp.id:
                    bets = BetRepository.get_bets_by_competitor(comp.id, limit=50)
                    round_bets = [b for b in bets if b.round_id == active_round.id]
                    st.caption(f"Apostas nesta rodada: {len(round_bets)}")

            with col_stats:
                st.markdown(f"🎯 **{comp.winning_bets} acerto(s)**")
                st.markdown(f"🪙 **R$ {comp.points:.2f}** saldo")

            with col_action:
                # Se for admin, exibe seletor de status inline para controle rápido
                if st.session_state.get("user_role") == "admin":
                    new_status = st.selectbox(
                        "Status",
                        options=["active", "inactive", "suspended"],
                        index=["active", "inactive", "suspended"].index(comp.status),
                        key=f"comp_status_{comp.id}",
                        label_visibility="collapsed",
                    )
                    if new_status != comp.status:
                        CompetitorRepository.update_competitor_status(comp.id, new_status)
                        st.rerun()
                else:
                    status_map = {
                        "active": "🟢 Ativo",
                        "inactive": "⚫ Inativo",
                        "suspended": "🔴 Suspenso",
                    }
                    st.markdown(
                        f"<div style='text-align: right; padding-top: 8px;'>{status_map.get(comp.status, comp.status)}</div>",
                        unsafe_allow_html=True,
                    )
