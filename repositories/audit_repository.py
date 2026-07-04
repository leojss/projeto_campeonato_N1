"""
repositories/audit_repository.py — Acesso ao banco para logs de auditoria.
"""

from __future__ import annotations

from typing import Optional, Any
from datetime import date

from config.supabase_client import get_admin_client
from models.audit import AuditLog


class AuditRepository:
    """Repositório de auditoria — sempre usa service role (bypass RLS)."""

    TABLE = "audit_logs"

    @staticmethod
    def log_event(
        action: str,
        actor_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> str | None:
        """
        Registra um evento de auditoria.

        Returns:
            ID do registro criado, ou None em caso de falha silenciosa.
        """
        try:
            client = get_admin_client()
            log = AuditLog(
                actor_id=actor_id,
                action=action,
                entity_name=entity_name,
                entity_id=str(entity_id) if entity_id else None,
                payload=payload,
            )
            result = (
                client.table(AuditRepository.TABLE)
                .insert(log.to_dict())
                .execute()
            )
            if result.data:
                return result.data[0]["id"]
        except Exception as e:
            # Auditoria nunca deve quebrar o fluxo principal
            print(f"[AuditRepository] Falha ao registrar evento '{action}': {e}")
        return None

    @staticmethod
    def get_recent_logs(limit: int = 100) -> list[AuditLog]:
        """Retorna os logs mais recentes."""
        client = get_admin_client()
        result = (
            client.table(AuditRepository.TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AuditLog.from_dict(row) for row in result.data]

    @staticmethod
    def get_logs_by_action(action: str, limit: int = 50) -> list[AuditLog]:
        """Filtra logs por tipo de ação."""
        client = get_admin_client()
        result = (
            client.table(AuditRepository.TABLE)
            .select("*")
            .eq("action", action)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AuditLog.from_dict(row) for row in result.data]

    @staticmethod
    def get_logs_by_actor(actor_id: str, limit: int = 50) -> list[AuditLog]:
        """Filtra logs por ator (usuário)."""
        client = get_admin_client()
        result = (
            client.table(AuditRepository.TABLE)
            .select("*")
            .eq("actor_id", actor_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AuditLog.from_dict(row) for row in result.data]

    @staticmethod
    def get_logs_by_date_range(start: date, end: date) -> list[AuditLog]:
        """Filtra logs por intervalo de datas."""
        client = get_admin_client()
        result = (
            client.table(AuditRepository.TABLE)
            .select("*")
            .gte("created_at", f"{start.isoformat()}T00:00:00")
            .lte("created_at", f"{end.isoformat()}T23:59:59")
            .order("created_at", desc=True)
            .execute()
        )
        return [AuditLog.from_dict(row) for row in result.data]
