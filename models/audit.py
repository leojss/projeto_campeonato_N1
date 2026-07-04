"""
models/audit.py — Modelo de domínio para logs de auditoria.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any


# Ações auditadas pelo sistema
class AuditAction:
    LOGIN               = "LOGIN"
    LOGOUT              = "LOGOUT"
    BET_SUBMITTED       = "BET_SUBMITTED"
    BET_REJECTED        = "BET_REJECTED"
    BET_APPROVED        = "BET_APPROVED"
    BET_MANUAL_ADJUST   = "BET_MANUAL_ADJUST"
    UPLOAD_ATTEMPTED    = "UPLOAD_ATTEMPTED"
    UPLOAD_BLOCKED      = "UPLOAD_BLOCKED"
    UPLOAD_COMPLETED    = "UPLOAD_COMPLETED"
    OCR_PROCESSED       = "OCR_PROCESSED"
    OCR_FAILED          = "OCR_FAILED"
    OCR_LOW_CONFIDENCE  = "OCR_LOW_CONFIDENCE"
    ROUND_OPENED        = "ROUND_OPENED"
    ROUND_CLOSED        = "ROUND_CLOSED"
    ROUND_FINALIZED     = "ROUND_FINALIZED"
    WINNER_DEFINED      = "WINNER_DEFINED"
    COMPETITOR_CREATED  = "COMPETITOR_CREATED"
    COMPETITOR_UPDATED  = "COMPETITOR_UPDATED"
    LIMIT_EXCEEDED      = "LIMIT_EXCEEDED"
    INVALID_ODD         = "INVALID_ODD"
    DUPLICATE_BLOCKED   = "DUPLICATE_BLOCKED"
    DEADLINE_EXCEEDED   = "DEADLINE_EXCEEDED"
    IMAGE_REPROCESSED   = "IMAGE_REPROCESSED"


@dataclass
class AuditLog:
    """Registro de auditoria de ação crítica no sistema."""
    id: Optional[str] = None
    actor_id: Optional[str] = None          # auth_user_id ou None (sistema)
    action: str = ""                        # Constante de AuditAction
    entity_name: Optional[str] = None      # Nome da tabela/entidade
    entity_id: Optional[str] = None        # UUID ou outro identificador
    payload: Optional[dict[str, Any]] = None  # Dados relevantes
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "actor_id": self.actor_id,
            "action": self.action,
            "entity_name": self.entity_name,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditLog":
        return cls(
            id=data.get("id"),
            actor_id=data.get("actor_id"),
            action=data.get("action", ""),
            entity_name=data.get("entity_name"),
            entity_id=data.get("entity_id"),
            payload=data.get("payload"),
            created_at=data.get("created_at"),
        )
