"""
agents/ranking.py — AgentRanking
Calcula ranking semanal, histórico e determina vencedor da rodada.
"""

from __future__ import annotations

from models.round import RankingEntry
from services.ranking_service import RankingService
from repositories.round_repository import RoundRepository
from repositories.audit_repository import AuditRepository
from repositories.competitor_repository import CompetitorRepository
from models.audit import AuditAction


class AgentRanking:
    """
    Agente de ranking — calcula posições, determina vencedor e atualiza banco.
    """

    def compute_ranking(self, round_id: str) -> list[RankingEntry]:
        """
        Calcula o ranking completo de uma rodada.

        Returns:
            Lista ordenada de RankingEntry com posições.
        """
        return RankingService.compute_weekly_ranking(round_id)

    def determine_winner(self, round_id: str, actor_id: str | None = None) -> str | None:
        """
        Determina e registra o vencedor da rodada.

        Returns:
            competitor_id do vencedor ou None.
        """
        winner_id = RankingService.determine_winner(round_id)

        if winner_id:
            # Busca nome do vencedor para o log
            winner = CompetitorRepository.get_competitor_by_id(winner_id)
            winner_name = winner.display_name if winner else winner_id

            AuditRepository.log_event(
                action=AuditAction.WINNER_DEFINED,
                actor_id=actor_id,
                entity_name="rounds",
                entity_id=round_id,
                payload={
                    "winner_competitor_id": winner_id,
                    "winner_name": winner_name,
                },
            )

        return winner_id

    def get_leaderboard(self, round_id: str, limit: int = 10) -> list[RankingEntry]:
        """Retorna o leaderboard para exibição na UI."""
        return RankingService.get_leaderboard(round_id, limit)
