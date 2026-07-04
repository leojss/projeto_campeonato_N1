"""
repositories/settlement_repository.py — Acesso ao banco para liquidações.
"""

from __future__ import annotations

from typing import Optional

from config.supabase_client import get_admin_client
from models.bet import Settlement


class SettlementRepository:
    """Repositório de liquidações de apostas."""

    TABLE = "settlements"

    @staticmethod
    def create_settlement(settlement: Settlement) -> Settlement:
        """Cria o registro de liquidação de uma aposta."""
        client = get_admin_client()
        result = (
            client.table(SettlementRepository.TABLE)
            .insert(settlement.to_dict())
            .execute()
        )
        data = result.data[0]
        settlement.id = data["id"]
        settlement.settled_at = data.get("settled_at")
        return settlement

    @staticmethod
    def get_settlement_by_bet(bet_id: str) -> Optional[Settlement]:
        """Retorna a liquidação de uma aposta."""
        client = get_admin_client()
        result = (
            client.table(SettlementRepository.TABLE)
            .select("*")
            .eq("bet_id", bet_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        return Settlement(
            id=row.get("id"),
            bet_id=row.get("bet_id"),
            settled_at=row.get("settled_at"),
            outcome=row.get("outcome", "loss"),
            gross_return=float(row["gross_return"]) if row.get("gross_return") is not None else None,
            net_profit=float(row["net_profit"]) if row.get("net_profit") is not None else None,
            created_at=row.get("created_at"),
        )

    @staticmethod
    def get_settlements_by_round(round_id: str) -> list[dict]:
        """
        Retorna liquidações agregadas por competidor em uma rodada.
        Retorna lista de dicts com: competitor_id, total_bets, winning_bets,
        net_profit, gross_return.
        """
        client = get_admin_client()
        # Query com join: settlements → bets (para obter round_id e competitor_id)
        result = (
            client.table(SettlementRepository.TABLE)
            .select("*, bets!inner(competitor_id, round_id, stake_value)")
            .eq("bets.round_id", round_id)
            .execute()
        )
        return result.data or []

    @staticmethod
    def upsert_settlement(settlement: Settlement) -> Settlement:
        """Insere ou atualiza uma liquidação (idempotente por bet_id)."""
        client = get_admin_client()
        result = (
            client.table(SettlementRepository.TABLE)
            .upsert(settlement.to_dict(), on_conflict="bet_id")
            .execute()
        )
        data = result.data[0]
        settlement.id = data["id"]
        return settlement
