"""
agents/auditoria.py — AgentAuditoria
Wrapper centralizado para registro de eventos de auditoria.
Garante que a auditoria nunca interrompe o fluxo principal.
"""

from __future__ import annotations

from typing import Optional, Any

from repositories.audit_repository import AuditRepository
from models.audit import AuditAction


class AgentAuditoria:
    """
    Agente de auditoria — registra eventos críticos do sistema.
    Todos os métodos são seguros (falham silenciosamente).
    """

    @staticmethod
    def log(
        action: str,
        actor_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Registra um evento genérico de auditoria."""
        return AuditRepository.log_event(
            action=action,
            actor_id=actor_id,
            entity_name=entity_name,
            entity_id=entity_id,
            payload=payload,
        )

    @staticmethod
    def log_login(actor_id: str, email: str) -> None:
        AgentAuditoria.log(
            AuditAction.LOGIN,
            actor_id=actor_id,
            payload={"email": email},
        )

    @staticmethod
    def log_logout(actor_id: str) -> None:
        AgentAuditoria.log(AuditAction.LOGOUT, actor_id=actor_id)

    @staticmethod
    def log_bet_submitted(actor_id: str, bet_id: str, status: str, confidence: float) -> None:
        AgentAuditoria.log(
            AuditAction.BET_SUBMITTED,
            actor_id=actor_id,
            entity_name="bets",
            entity_id=bet_id,
            payload={"final_status": status, "ocr_confidence": confidence},
        )

    @staticmethod
    def log_bet_rejected(actor_id: str, reason: str, payload: Optional[dict] = None) -> None:
        AgentAuditoria.log(
            AuditAction.BET_REJECTED,
            actor_id=actor_id,
            payload={"reason": reason, **(payload or {})},
        )

    @staticmethod
    def log_upload_blocked(actor_id: str, target_date: str, reason: str) -> None:
        AgentAuditoria.log(
            AuditAction.UPLOAD_BLOCKED,
            actor_id=actor_id,
            payload={"target_date": target_date, "reason": reason},
        )

    @staticmethod
    def log_upload_completed(actor_id: str, bet_id: str, storage_path: str) -> None:
        AgentAuditoria.log(
            AuditAction.UPLOAD_COMPLETED,
            actor_id=actor_id,
            entity_name="bets",
            entity_id=bet_id,
            payload={"storage_path": storage_path},
        )

    @staticmethod
    def log_ocr_processed(bet_id: str, confidence: float, status: str) -> None:
        AgentAuditoria.log(
            AuditAction.OCR_PROCESSED,
            entity_name="bet_images",
            entity_id=bet_id,
            payload={"confidence": confidence, "status": status},
        )

    @staticmethod
    def log_ocr_failed(bet_id: str, error: str) -> None:
        AgentAuditoria.log(
            AuditAction.OCR_FAILED,
            entity_name="bet_images",
            entity_id=bet_id,
            payload={"error": error},
        )

    @staticmethod
    def log_round_closed(actor_id: str, round_id: str) -> None:
        AgentAuditoria.log(
            AuditAction.ROUND_CLOSED,
            actor_id=actor_id,
            entity_name="rounds",
            entity_id=round_id,
        )

    @staticmethod
    def log_round_finalized(actor_id: str, round_id: str, winner_id: Optional[str]) -> None:
        AgentAuditoria.log(
            AuditAction.ROUND_FINALIZED,
            actor_id=actor_id,
            entity_name="rounds",
            entity_id=round_id,
            payload={"winner_competitor_id": winner_id},
        )

    @staticmethod
    def log_manual_adjustment(actor_id: str, bet_id: str, old_status: str, new_status: str, notes: str) -> None:
        AgentAuditoria.log(
            AuditAction.BET_MANUAL_ADJUST,
            actor_id=actor_id,
            entity_name="bets",
            entity_id=bet_id,
            payload={
                "old_status": old_status,
                "new_status": new_status,
                "notes": notes,
            },
        )

    @staticmethod
    def log_deadline_exceeded(actor_id: str, target_date: str) -> None:
        AgentAuditoria.log(
            AuditAction.DEADLINE_EXCEEDED,
            actor_id=actor_id,
            payload={"target_date": target_date},
        )

    @staticmethod
    def log_limit_exceeded(actor_id: str, target_date: str, current_count: int) -> None:
        AgentAuditoria.log(
            AuditAction.LIMIT_EXCEEDED,
            actor_id=actor_id,
            payload={"target_date": target_date, "current_count": current_count},
        )
