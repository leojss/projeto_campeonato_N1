"""
tests/test_ranking_service.py — Testes do RankingService.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from services.ranking_service import RankingService
from models.bet import Bet, Settlement
from models.round import RankingEntry
from models.competitor import Competitor


def _make_bet(competitor_id: str, bet_id: str) -> Bet:
    bet = Bet()
    bet.id = bet_id
    bet.competitor_id = competitor_id
    bet.status = "settled"
    bet.stake_value = 100.0
    bet.total_odd = 2.0
    bet.submitted_at = datetime(2026, 6, 1, 10, 0, 0)
    return bet


def _make_settlement(bet_id: str, outcome: str, net_profit: float, gross_return: float = None) -> Settlement:
    s = Settlement()
    s.bet_id = bet_id
    s.outcome = outcome
    s.net_profit = net_profit
    s.gross_return = gross_return or (net_profit + 100 if outcome == "win" else None)
    return s


class TestRankingService:

    @patch("services.ranking_service.CompetitorRepository.get_all_competitors")
    @patch("services.ranking_service.SettlementRepository.get_settlement_by_bet")
    @patch("services.ranking_service.BetRepository.get_bets_by_round")
    def test_ranking_ordered_by_profit(self, mock_bets, mock_settlement, mock_competitors):
        """Competidor com maior lucro deve ser o primeiro."""
        comp_a = "comp-a"
        comp_b = "comp-b"

        mock_bets.return_value = [
            _make_bet(comp_a, "bet-a1"),
            _make_bet(comp_b, "bet-b1"),
        ]

        def get_settlement(bet_id):
            if bet_id == "bet-a1":
                return _make_settlement("bet-a1", "win", 150.0)  # Lucro R$150
            return _make_settlement("bet-b1", "win", 80.0)       # Lucro R$80

        mock_settlement.side_effect = get_settlement

        mock_competitors.return_value = [
            Competitor(id=comp_a, display_name="Alice"),
            Competitor(id=comp_b, display_name="Bob"),
        ]

        ranking = RankingService.compute_weekly_ranking("round-1")

        assert len(ranking) == 2
        assert ranking[0].competitor_id == comp_a   # Alice tem maior lucro
        assert ranking[0].position == 1
        assert ranking[1].competitor_id == comp_b
        assert ranking[1].position == 2

    @patch("services.ranking_service.CompetitorRepository.get_all_competitors")
    @patch("services.ranking_service.SettlementRepository.get_settlement_by_bet")
    @patch("services.ranking_service.BetRepository.get_bets_by_round")
    def test_tiebreaker_by_winning_bets(self, mock_bets, mock_settlement, mock_competitors):
        """Em caso de empate de lucro, quem ganhou mais apostas fica na frente."""
        comp_a = "comp-a"
        comp_b = "comp-b"

        mock_bets.return_value = [
            _make_bet(comp_a, "bet-a1"),
            _make_bet(comp_a, "bet-a2"),
            _make_bet(comp_b, "bet-b1"),
        ]

        def get_settlement(bet_id):
            if bet_id in ("bet-a1", "bet-a2"):
                return _make_settlement(bet_id, "win", 50.0)  # 2 wins, lucro total 100
            return _make_settlement("bet-b1", "win", 100.0)   # 1 win, lucro total 100

        mock_settlement.side_effect = get_settlement

        mock_competitors.return_value = [
            Competitor(id=comp_a, display_name="Alice"),
            Competitor(id=comp_b, display_name="Bob"),
        ]

        ranking = RankingService.compute_weekly_ranking("round-1")

        # Empate em lucro (100), Alice ganha por ter mais apostas vencedoras (2 vs 1)
        assert ranking[0].competitor_id == comp_a

    @patch("services.ranking_service.BetRepository.get_bets_by_round")
    def test_empty_round_returns_empty_ranking(self, mock_bets):
        mock_bets.return_value = []
        ranking = RankingService.compute_weekly_ranking("round-empty")
        assert ranking == []

    @patch("services.ranking_service.BetRepository.get_bets_by_round")
    def test_only_non_settled_bets_ignored(self, mock_bets):
        """Apostas não liquidadas não devem entrar no ranking."""
        bet = _make_bet("comp-a", "bet-1")
        bet.status = "approved"  # Não é "settled"
        mock_bets.return_value = [bet]
        ranking = RankingService.compute_weekly_ranking("round-1")
        assert ranking == []
