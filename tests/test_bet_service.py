"""
tests/test_bet_service.py — Testes unitários do BetService.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from services.bet_service import BetService, BetValidationError
from models.bet import BetSelection


# ===========================
# Fixtures
# ===========================

def _make_selection(odd: float = 2.0, desc: str = "Seleção teste") -> BetSelection:
    return BetSelection(description=desc, odd=odd)


def _future_date() -> date:
    return date.today() + timedelta(days=2)


# ===========================
# calculate_total_odd
# ===========================

class TestCalculateTotalOdd:
    def test_single_selection(self):
        selections = [_make_selection(2.50)]
        assert BetService.calculate_total_odd(selections) == 2.50

    def test_two_selections(self):
        selections = [_make_selection(2.0), _make_selection(1.8)]
        result = BetService.calculate_total_odd(selections)
        assert abs(result - 3.60) < 0.0001

    def test_three_selections(self):
        selections = [_make_selection(2.0), _make_selection(2.0), _make_selection(2.0)]
        result = BetService.calculate_total_odd(selections)
        assert abs(result - 8.0) < 0.0001

    def test_empty_selections_raises(self):
        with pytest.raises(BetValidationError):
            BetService.calculate_total_odd([])


# ===========================
# calculate_gross_return
# ===========================

class TestCalculateGrossReturn:
    def test_basic_calculation(self):
        assert BetService.calculate_gross_return(100.0, 2.5) == 250.0

    def test_stake_zero(self):
        assert BetService.calculate_gross_return(0.0, 3.0) == 0.0

    def test_odd_one(self):
        assert BetService.calculate_gross_return(50.0, 1.0) == 50.0


# ===========================
# calculate_net_profit
# ===========================

class TestCalculateNetProfit:
    def test_win(self):
        result = BetService.calculate_net_profit(250.0, 100.0, won=True)
        assert result == 150.0

    def test_loss(self):
        result = BetService.calculate_net_profit(None, 100.0, won=False)
        assert result == -100.0

    def test_void_treated_as_loss(self):
        result = BetService.calculate_net_profit(None, 50.0, won=False)
        assert result == -50.0


# ===========================
# validate_bet_rules
# ===========================

class TestValidateBetRules:
    COMPETITOR_ID = "comp-uuid-123"

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=0)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_valid_bet_passes(self, mock_deadline, mock_count):
        selections = [_make_selection(2.0)]
        # Não deve lançar exceção
        BetService.validate_bet_rules(self.COMPETITOR_ID, _future_date(), selections, 50.0)

    @patch("services.bet_service.is_deadline_passed", return_value=True)
    def test_deadline_passed_raises(self, mock_deadline):
        with pytest.raises(BetValidationError, match="Prazo expirado"):
            BetService.validate_bet_rules(
                self.COMPETITOR_ID, date.today(), [_make_selection()], 50.0
            )

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=2)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_daily_limit_exceeded_raises(self, mock_deadline, mock_count):
        with pytest.raises(BetValidationError, match="Limite diário"):
            BetService.validate_bet_rules(
                self.COMPETITOR_ID, _future_date(), [_make_selection()], 50.0
            )

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=0)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_too_many_selections_raises(self, mock_deadline, mock_count):
        selections = [_make_selection() for _ in range(4)]  # 4 seleções (máx é 3)
        with pytest.raises(BetValidationError, match="excede o limite"):
            BetService.validate_bet_rules(self.COMPETITOR_ID, _future_date(), selections, 50.0)

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=0)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_odd_below_minimum_raises(self, mock_deadline, mock_count):
        selections = [_make_selection(odd=1.30)]  # Abaixo de 1.50
        with pytest.raises(BetValidationError, match="inferior ao mínimo"):
            BetService.validate_bet_rules(self.COMPETITOR_ID, _future_date(), selections, 50.0)

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=0)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_stake_zero_raises(self, mock_deadline, mock_count):
        selections = [_make_selection()]
        with pytest.raises(BetValidationError, match="maior que zero"):
            BetService.validate_bet_rules(self.COMPETITOR_ID, _future_date(), selections, 0.0)

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=0)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_exactly_min_odd_passes(self, mock_deadline, mock_count):
        selections = [_make_selection(odd=1.50)]  # Exatamente no mínimo
        BetService.validate_bet_rules(self.COMPETITOR_ID, _future_date(), selections, 10.0)

    @patch("services.bet_service.BetRepository.count_bets_today", return_value=1)
    @patch("services.bet_service.is_deadline_passed", return_value=False)
    def test_first_bet_of_day_passes(self, mock_deadline, mock_count):
        """Deve passar — 1 aposta é permitida (máximo é 2)."""
        selections = [_make_selection()]
        BetService.validate_bet_rules(self.COMPETITOR_ID, _future_date(), selections, 10.0)
