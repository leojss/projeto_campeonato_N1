"""
tests/test_validators.py — Testes do AgentValidadorRegras.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from agents.validador_regras import AgentValidadorRegras
from agents.normalizacao_aposta import NormalizedBet
from models.bet import BetSelection


def _make_selection(odd: float = 2.0) -> BetSelection:
    return BetSelection(description="Seleção teste", odd=odd)


def _future_date() -> date:
    return date.today() + timedelta(days=2)


def _make_normalized(
    selections=None,
    confidence: float = 0.90,
    target_date=None,
) -> NormalizedBet:
    if selections is None:
        selections = [_make_selection()]
    return NormalizedBet(
        target_date=target_date or _future_date(),
        total_odd=2.0,
        aposta_descricao="Seleção teste",
        selections=selections,
        ocr_confidence=confidence,
    )


class TestAgentValidadorRegras:
    agent = AgentValidadorRegras()
    COMPETITOR_ID = "00000000-0000-0000-0000-000000000001"

    @patch("agents.validador_regras.BetRepository.count_bets_today", return_value=0)
    @patch("agents.validador_regras.is_deadline_passed", return_value=False)
    def test_valid_bet_approved(self, mock_dl, mock_count):
        normalized = _make_normalized()
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.is_approved
        assert not result.errors

    @patch("agents.validador_regras.is_deadline_passed", return_value=True)
    def test_expired_deadline_rejected(self, mock_dl):
        normalized = _make_normalized()
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.is_rejected
        assert any("Prazo" in e for e in result.errors)

    @patch("agents.validador_regras.BetRepository.count_bets_today", return_value=2)
    @patch("agents.validador_regras.is_deadline_passed", return_value=False)
    def test_daily_limit_exceeded_rejected(self, mock_dl, mock_count):
        normalized = _make_normalized()
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.is_rejected
        assert any("Limite diário" in e for e in result.errors)

    @patch("agents.validador_regras.BetRepository.count_bets_today", return_value=0)
    @patch("agents.validador_regras.is_deadline_passed", return_value=False)
    def test_odd_below_min_rejected(self, mock_dl, mock_count):
        normalized = _make_normalized(selections=[_make_selection(odd=1.30)])
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.is_rejected
        assert any("odd" in e.lower() for e in result.errors)

    @patch("agents.validador_regras.BetRepository.count_bets_today", return_value=0)
    @patch("agents.validador_regras.is_deadline_passed", return_value=False)
    def test_too_many_selections_rejected(self, mock_dl, mock_count):
        selections = [_make_selection() for _ in range(4)]
        normalized = _make_normalized(selections=selections)
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.is_rejected

    @patch("agents.validador_regras.BetRepository.count_bets_today", return_value=0)
    @patch("agents.validador_regras.is_deadline_passed", return_value=False)
    def test_low_confidence_goes_to_review(self, mock_dl, mock_count):
        normalized = _make_normalized(confidence=0.50)  # Abaixo de 0.75
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.needs_review
        assert any("Confiança" in w for w in result.warnings)

    @patch("agents.validador_regras.BetRepository.count_bets_today", return_value=0)
    @patch("agents.validador_regras.is_deadline_passed", return_value=False)
    def test_no_selections_rejected(self, mock_dl, mock_count):
        normalized = _make_normalized(selections=[])
        result = self.agent.validate(normalized, self.COMPETITOR_ID)
        assert result.is_rejected
        assert any("seleção" in e.lower() for e in result.errors)
