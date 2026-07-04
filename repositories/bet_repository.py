"""
repositories/bet_repository.py — Acesso ao banco para apostas.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from config.supabase_client import get_admin_client
from models.bet import Bet, BetSelection


class BetRepository:
    """Repositório de operações CRUD para apostas."""

    TABLE = "bets"
    SELECTIONS_TABLE = "bet_selections"

    @staticmethod
    def create_bet(bet: Bet) -> Bet:
        """
        Insere uma nova aposta no banco.

        Args:
            bet: Objeto Bet preenchido.

        Returns:
            Bet com id preenchido pelo banco.
        """
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .insert(bet.to_dict())
            .execute()
        )
        data = result.data[0]
        bet.id = data["id"]
        bet.created_at = data.get("created_at")
        return bet

    @staticmethod
    def create_selections(selections: list[BetSelection]) -> list[BetSelection]:
        """Insere múltiplas seleções de uma aposta."""
        if not selections:
            return []
        client = get_admin_client()
        payload = [s.to_dict() for s in selections]
        result = (
            client.table(BetRepository.SELECTIONS_TABLE)
            .insert(payload)
            .execute()
        )
        for i, data in enumerate(result.data):
            selections[i].id = data["id"]
        return selections

    @staticmethod
    def get_bets_by_competitor(competitor_id: str, limit: int = 50) -> list[Bet]:
        """Retorna as apostas de um competidor, ordenadas por data decrescente."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .select("*")
            .eq("competitor_id", competitor_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [Bet.from_dict(row) for row in result.data]

    @staticmethod
    def get_all_bets(limit: int = 100) -> list[Bet]:
        """Retorna todas as apostas no banco de dados, ordenadas por data decrescente."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [Bet.from_dict(row) for row in result.data]

    @staticmethod
    def get_bets_by_round(round_id: str) -> list[Bet]:
        """Retorna todas as apostas de uma rodada."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .select("*")
            .eq("round_id", round_id)
            .order("submitted_at", desc=False)
            .execute()
        )
        return [Bet.from_dict(row) for row in result.data]

    @staticmethod
    def count_bets_today(competitor_id: str, target_date: date, exclude_bet_id: Optional[str] = None) -> int:
        """
        Conta apostas válidas de um competidor para uma data específica.
        Exclui apostas rejeitadas e rascunhos. Permite excluir uma aposta específica por ID.
        """
        client = get_admin_client()
        query = (
            client.table(BetRepository.TABLE)
            .select("id", count="exact")
            .eq("competitor_id", competitor_id)
            .eq("target_date", target_date.isoformat())
            .not_.in_("status", ["rejected", "draft"])
        )
        if exclude_bet_id:
            query = query.neq("id", exclude_bet_id)
        result = query.execute()
        return result.count or 0

    @staticmethod
    def get_bet_by_id(bet_id: str) -> Optional[Bet]:
        """Retorna uma aposta por ID."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .select("*")
            .eq("id", bet_id)
            .single()
            .execute()
        )
        if result.data:
            return Bet.from_dict(result.data)
        return None

    @staticmethod
    def update_bet_status(bet_id: str, status: str, notes: str | None = None) -> bool:
        """Atualiza o status de uma aposta."""
        payload: dict = {"status": status}
        if notes is not None:
            payload["notes"] = notes
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .update(payload)
            .eq("id", bet_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def update_bet(bet_id: str, bet_data: dict) -> bool:
        """Atualiza campos arbitrários de uma aposta (usado na persistência pós-OCR)."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .update(bet_data)
            .eq("id", bet_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def update_bet_confidence(bet_id: str, confidence: float) -> bool:
        """Atualiza o score de confiança da leitura da IA."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .update({"ocr_confidence": confidence})
            .eq("id", bet_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def lock_bet(bet_id: str) -> bool:
        """Bloqueia uma aposta (impede edição)."""
        return BetRepository.update_bet_status(bet_id, "locked")

    @staticmethod
    def get_selections_by_bet(bet_id: str) -> list[BetSelection]:
        """Retorna as seleções de uma aposta."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.SELECTIONS_TABLE)
            .select("*")
            .eq("bet_id", bet_id)
            .order("selection_order")
            .execute()
        )
        selections = []
        for row in result.data:
            selections.append(BetSelection(
                id=row.get("id"),
                bet_id=row.get("bet_id"),
                selection_order=row.get("selection_order", 1),
                description=row.get("description", ""),
                odd=float(row.get("odd", 1.5)),
                event_name=row.get("event_name"),
                event_datetime=row.get("event_datetime"),
                result_status=row.get("result_status", "pending"),
                api_fixture_id=row.get("api_fixture_id"),
                resolved_at=row.get("resolved_at"),
                resolution_source=row.get("resolution_source"),
                created_at=row.get("created_at"),
            ))
        return selections

    @staticmethod
    def get_pending_review_bets() -> list[Bet]:
        """Retorna apostas aguardando revisão manual."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .select("*")
            .in_("status", ["review", "processing"])
            .execute()
        )
        return [Bet.from_dict(row) for row in result.data]

    @staticmethod
    def delete_bet(bet_id: str) -> bool:
        """Deleta uma aposta do banco de dados (cascade limpa seleções e imagens automaticamente)."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.TABLE)
            .delete()
            .eq("id", bet_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def update_selection(selection_id: str, selection_data: dict) -> bool:
        """Atualiza campos arbitrários de uma seleção (status, odd, etc.)."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.SELECTIONS_TABLE)
            .update(selection_data)
            .eq("id", selection_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def get_pending_selections() -> list[BetSelection]:
        """Retorna todas as seleções com status 'pending'."""
        client = get_admin_client()
        result = (
            client.table(BetRepository.SELECTIONS_TABLE)
            .select("*")
            .eq("result_status", "pending")
            .execute()
        )
        selections = []
        for row in result.data:
            selections.append(BetSelection(
                id=row.get("id"),
                bet_id=row.get("bet_id"),
                selection_order=row.get("selection_order", 1),
                description=row.get("description", ""),
                odd=float(row.get("odd", 1.5)),
                event_name=row.get("event_name"),
                event_datetime=row.get("event_datetime"),
                result_status=row.get("result_status", "pending"),
                api_fixture_id=row.get("api_fixture_id"),
                resolved_at=row.get("resolved_at"),
                resolution_source=row.get("resolution_source"),
                created_at=row.get("created_at"),
            ))
        return selections
