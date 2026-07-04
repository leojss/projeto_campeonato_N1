"""
tests/test_round_service.py — Testes do RoundService.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from services.round_service import RoundService
from models.round import Round


def _open_round(end_date: date = None) -> Round:
    r = Round()
    r.id = "round-uuid-1"
    r.status = "open"
    r.end_date = end_date or date.today() + timedelta(days=3)
    r.start_date = r.end_date - timedelta(days=6)
    r.competition_id = "c0000000-0000-0000-0000-000000000001"
    r.week_number = 26
    return r


class TestRoundService:

    @patch("services.round_service.RoundRepository.get_active_round")
    def test_get_active_round_returns_open_round(self, mock_get):
        mock_round = _open_round()
        mock_get.return_value = mock_round
        result = RoundService.get_active_round()
        assert result is not None
        assert result.is_open

    @patch("services.round_service.RoundRepository.get_active_round")
    def test_get_active_round_returns_none_when_no_open(self, mock_get):
        mock_get.return_value = None
        result = RoundService.get_active_round()
        assert result is None

    @patch("services.round_service.RoundRepository.update_round_status", return_value=True)
    @patch("services.round_service.RoundRepository.get_active_round")
    def test_close_round_changes_status(self, mock_get, mock_update):
        mock_round = _open_round()
        mock_get.return_value = mock_round
        result = RoundService.close_round(mock_round.id)
        mock_update.assert_called_once_with(mock_round.id, "closed")
        assert result is True

    @patch("services.round_service.RoundRepository.create_round")
    @patch("services.round_service.RoundRepository.get_active_round")
    def test_ensure_active_round_creates_if_none(self, mock_get, mock_create):
        mock_get.return_value = None
        new_round = _open_round()
        mock_create.return_value = new_round
        result = RoundService.ensure_active_round()
        mock_create.assert_called_once()
        assert result is not None

    @patch("services.round_service.RoundRepository.get_active_round")
    def test_ensure_active_round_returns_existing(self, mock_get):
        existing = _open_round()
        mock_get.return_value = existing
        result = RoundService.ensure_active_round()
        assert result.id == existing.id

    @patch("services.round_service.get_today_br")
    @patch("services.round_service.RoundRepository.update_round_status")
    @patch("services.round_service.RoundRepository.get_active_round")
    def test_auto_close_when_end_date_passed(self, mock_get, mock_update, mock_today):
        """Rodada deve ser fechada automaticamente se today > end_date."""
        past_round = _open_round(end_date=date.today() - timedelta(days=1))
        mock_get.return_value = past_round
        mock_today.return_value = date.today()
        mock_update.return_value = True

        closed = RoundService.check_and_auto_close()
        assert closed is True
        mock_update.assert_called_once_with(past_round.id, "closed")

    @patch("services.round_service.get_today_br")
    @patch("services.round_service.RoundRepository.get_active_round")
    def test_no_auto_close_when_round_still_active(self, mock_get, mock_today):
        """Rodada não deve ser fechada se ainda está dentro do prazo."""
        active = _open_round(end_date=date.today() + timedelta(days=2))
        mock_get.return_value = active
        mock_today.return_value = date.today()

        closed = RoundService.check_and_auto_close()
        assert closed is False
