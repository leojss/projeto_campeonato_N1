"""
services/ranking_service.py — Cálculo de ranking semanal e determinação de vencedor.
"""

from __future__ import annotations

from typing import Optional

from models.round import RankingEntry
from repositories.bet_repository import BetRepository
from repositories.settlement_repository import SettlementRepository
from repositories.competitor_repository import CompetitorRepository


class RankingService:
    """Serviço de cálculo e exibição do ranking semanal."""

    @staticmethod
    def compute_weekly_ranking(round_id: str) -> list[RankingEntry]:
        """
        Calcula o ranking semanal com base nas liquidações da rodada.

        Critérios de ordenação (em ordem de prioridade):
        1. Maior lucro líquido acumulado
        2. Maior número de apostas ganhas
        3. Maior taxa de acerto
        4. Data/hora da última submissão válida mais antiga (mais consistente)

        Returns:
            Lista de RankingEntry ordenada por posição.
        """
        # Busca todas as apostas da rodada com status settled
        bets = BetRepository.get_bets_by_round(round_id)

        # Agrupa por competidor
        stats: dict[str, dict] = {}

        for bet in bets:
            if bet.status != "settled":
                continue
            cid = bet.competitor_id
            if cid not in stats:
                stats[cid] = {
                    "total_bets": 0,
                    "winning_bets": 0,
                    "net_profit": 0.0,
                    "gross_return": 0.0,
                    "last_submission": None,
                }

            stats[cid]["total_bets"] += 1
            if bet.submitted_at:
                last = stats[cid]["last_submission"]
                if last is None or bet.submitted_at > last:
                    stats[cid]["last_submission"] = bet.submitted_at

            # Busca liquidação para este bet
            settlement = SettlementRepository.get_settlement_by_bet(bet.id)
            if settlement:
                stats[cid]["net_profit"] += settlement.net_profit or 0.0
                stats[cid]["gross_return"] += settlement.gross_return or 0.0
                if settlement.outcome == "win":
                    stats[cid]["winning_bets"] += 1

        if not stats:
            return []

        # Busca nomes dos competidores
        all_competitors = CompetitorRepository.get_all_competitors()
        comp_map = {c.id: c.display_name for c in all_competitors}

        # Monta entradas
        entries: list[RankingEntry] = []
        for cid, data in stats.items():
            total = data["total_bets"]
            win_rate = data["winning_bets"] / total if total > 0 else 0.0
            entries.append(RankingEntry(
                competitor_id=cid,
                display_name=comp_map.get(cid, "Desconhecido"),
                total_bets=total,
                winning_bets=data["winning_bets"],
                net_profit=data["net_profit"],
                gross_return=data["gross_return"],
                win_rate=win_rate,
                last_submission=data["last_submission"],
            ))

        # Ordena: 1) lucro (desc), 2) apostas ganhas (desc), 3) taxa acerto (desc),
        #          4) última submissão (asc → mais antigo = mais consistente)
        entries.sort(key=lambda e: (
            -e.net_profit,
            -e.winning_bets,
            -e.win_rate,
            e.last_submission or "",
        ))

        # Atribui posições
        for pos, entry in enumerate(entries, 1):
            entry.position = pos

        return entries

    @staticmethod
    def determine_winner(round_id: str) -> Optional[str]:
        """
        Determina o vencedor da rodada aplicando os critérios de desempate.

        Returns:
            competitor_id do vencedor, ou None se não houver apostas liquidadas.
        """
        ranking = RankingService.compute_weekly_ranking(round_id)
        if not ranking:
            return None
        return ranking[0].competitor_id

    @staticmethod
    def get_leaderboard(round_id: str, limit: int = 10) -> list[RankingEntry]:
        """Retorna o top-N do ranking para exibição na UI."""
        return RankingService.compute_weekly_ranking(round_id)[:limit]
