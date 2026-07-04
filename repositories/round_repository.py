"""
repositories/round_repository.py — Acesso ao banco para rodadas e competições.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from config.supabase_client import get_admin_client
from config.settings import ACTIVE_COMPETITION_ID
from models.round import Round, Competition


class RoundRepository:
    """Repositório de rodadas e competições."""

    ROUNDS_TABLE = "rounds"
    COMPETITIONS_TABLE = "competitions"

    @staticmethod
    def get_active_round() -> Optional[Round]:
        """Retorna a rodada com status 'open' da competição ativa."""
        client = get_admin_client()
        result = (
            client.table(RoundRepository.ROUNDS_TABLE)
            .select("*")
            .eq("competition_id", ACTIVE_COMPETITION_ID)
            .eq("status", "open")
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Round.from_dict(result.data[0])

    @staticmethod
    def get_round_by_id(round_id: str) -> Optional[Round]:
        """Retorna uma rodada pelo ID."""
        client = get_admin_client()
        result = (
            client.table(RoundRepository.ROUNDS_TABLE)
            .select("*")
            .eq("id", round_id)
            .single()
            .execute()
        )
        if result.data:
            return Round.from_dict(result.data)
        return None

    @staticmethod
    def create_round(round_obj: Round) -> Round:
        """Cria uma nova rodada."""
        client = get_admin_client()
        result = (
            client.table(RoundRepository.ROUNDS_TABLE)
            .insert(round_obj.to_dict())
            .execute()
        )
        data = result.data[0]
        round_obj.id = data["id"]
        return round_obj

    @staticmethod
    def update_round_status(round_id: str, status: str) -> bool:
        """Atualiza o status de uma rodada."""
        payload: dict = {"status": status}
        if status == "closed":
            payload["closed_at"] = datetime.utcnow().isoformat()
        client = get_admin_client()
        result = (
            client.table(RoundRepository.ROUNDS_TABLE)
            .update(payload)
            .eq("id", round_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def set_round_winner(round_id: str, winner_competitor_id: str) -> bool:
        """Define o vencedor de uma rodada."""
        client = get_admin_client()
        result = (
            client.table(RoundRepository.ROUNDS_TABLE)
            .update({
                "winner_competitor_id": winner_competitor_id,
                "status": "finalized",
            })
            .eq("id", round_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def get_all_rounds(limit: int = 20) -> list[Round]:
        """Retorna todas as rodadas da competição ativa."""
        client = get_admin_client()
        result = (
            client.table(RoundRepository.ROUNDS_TABLE)
            .select("*")
            .eq("competition_id", ACTIVE_COMPETITION_ID)
            .order("week_number", desc=True)
            .limit(limit)
            .execute()
        )
        return [Round.from_dict(row) for row in result.data]

    @staticmethod
    def get_active_competition() -> Optional[Competition]:
        """Retorna a competição ativa."""
        client = get_admin_client()
        result = (
            client.table(RoundRepository.COMPETITIONS_TABLE)
            .select("*")
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Competition.from_dict(result.data[0])
