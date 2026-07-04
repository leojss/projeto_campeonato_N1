"""
services/round_service.py — Gestão do ciclo de vida das rodadas semanais.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from config.settings import ACTIVE_COMPETITION_ID
from models.round import Round
from repositories.round_repository import RoundRepository
from services.ranking_service import RankingService
from utils.datetime_utils import get_today_br, get_current_week_range


class RoundService:
    """Serviço de ciclo de vida das rodadas semanais."""

    @staticmethod
    def get_active_round() -> Optional[Round]:
        """Retorna a rodada atualmente aberta."""
        return RoundRepository.get_active_round()

    @staticmethod
    def ensure_active_round() -> Round:
        """
        Garante que existe uma rodada aberta.
        Se não houver, cria uma nova para a semana corrente.

        Returns:
            Rodada aberta.
        """
        active = RoundRepository.get_active_round()
        if active:
            return active

        return RoundService.create_current_week_round()

    @staticmethod
    def create_current_week_round() -> Round:
        """Cria a rodada da semana atual."""
        sunday, saturday = get_current_week_range()
        week_number = int(sunday.strftime("%W"))  # semana do ano

        new_round = Round(
            competition_id=ACTIVE_COMPETITION_ID,
            week_number=week_number,
            start_date=sunday,
            end_date=saturday,
            status="open",
        )
        return RoundRepository.create_round(new_round)

    @staticmethod
    def close_round(round_id: str) -> bool:
        """
        Fecha uma rodada manualmente (admin).
        Não calcula vencedor — use finalize_round para isso.

        Returns:
            True se bem-sucedido.
        """
        return RoundRepository.update_round_status(round_id, "closed")

    @staticmethod
    def finalize_round(round_id: str) -> Optional[str]:
        """
        Finaliza uma rodada: calcula o ranking, define o vencedor e
        atualiza o status para 'finalized'.

        Returns:
            competitor_id do vencedor, ou None.
        """
        winner_id = RankingService.determine_winner(round_id)

        if winner_id:
            RoundRepository.set_round_winner(round_id, winner_id)
        else:
            RoundRepository.update_round_status(round_id, "finalized")

        return winner_id

    @staticmethod
    def check_and_auto_close() -> bool:
        """
        Verifica se a rodada ativa deve ser fechada automaticamente
        (sábado após 23:59).

        Returns:
            True se a rodada foi fechada.
        """
        active = RoundRepository.get_active_round()
        if not active:
            return False

        today = get_today_br()
        # Se hoje é após o end_date da rodada, fechar automaticamente
        if active.end_date and today > active.end_date:
            RoundRepository.update_round_status(active.id, "closed")
            return True

        return False
