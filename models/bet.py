"""
models/bet.py — Modelos de domínio para apostas e entidades relacionadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class BetSelection:
    """Seleção individual de uma aposta (uma das até 3 combinadas)."""
    id: Optional[str] = None
    bet_id: Optional[str] = None
    selection_order: int = 1
    description: str = ""
    odd: float = 1.50
    event_name: Optional[str] = None
    event_datetime: Optional[datetime] = None
    result_status: str = "pending"  # pending | won | lost | void | push
    api_fixture_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_source: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "bet_id": self.bet_id,
            "selection_order": self.selection_order,
            "description": self.description,
            "odd": self.odd,
            "event_name": self.event_name,
            "event_datetime": self.event_datetime.isoformat() if self.event_datetime else None,
            "result_status": self.result_status,
            "api_fixture_id": self.api_fixture_id,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_source": self.resolution_source,
        }


@dataclass
class BetImage:
    """Imagem enviada pelo competidor e resultado do processamento por IA."""
    id: Optional[str] = None
    bet_id: Optional[str] = None
    storage_path: str = ""
    original_filename: str = ""
    mime_type: str = ""
    file_size: int = 0
    uploaded_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    ocr_text: Optional[str] = None
    ocr_json: Optional[dict] = None
    confidence_score: Optional[float] = None
    status: str = "pending"  # pending | processing | extracted | failed | approved | rejected

    def to_dict(self) -> dict:
        return {
            "bet_id": self.bet_id,
            "storage_path": self.storage_path,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "status": self.status,
        }


@dataclass
class Settlement:
    """Liquidação e resultado financeiro de uma aposta."""
    id: Optional[str] = None
    bet_id: Optional[str] = None
    settled_at: Optional[datetime] = None
    outcome: str = "loss"           # win | loss | void
    gross_return: Optional[float] = None
    net_profit: Optional[float] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "bet_id": self.bet_id,
            "outcome": self.outcome,
            "gross_return": self.gross_return,
            "net_profit": self.net_profit,
        }


@dataclass
class Bet:
    """Aposta principal com todas as suas entidades relacionadas."""
    id: Optional[str] = None
    competitor_id: Optional[str] = None
    round_id: Optional[str] = None
    target_date: Optional[date] = None
    submitted_at: Optional[datetime] = None
    stake_value: float = 0.0
    total_odd: float = 1.50
    combined_count: int = 1
    status: str = "draft"           # draft | submitted | processing | approved | rejected | locked | settled | review
    deadline_at: Optional[datetime] = None
    ocr_confidence: Optional[float] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Entidades relacionadas (carregadas separadamente)
    selections: list[BetSelection] = field(default_factory=list)
    image: Optional[BetImage] = None
    settlement: Optional[Settlement] = None

    def to_dict(self) -> dict:
        """Serializa para inserção no Supabase (sem relações)."""
        return {
            "competitor_id": self.competitor_id,
            "round_id": self.round_id,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "stake_value": self.stake_value,
            "total_odd": self.total_odd,
            "combined_count": self.combined_count,
            "status": self.status,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "ocr_confidence": self.ocr_confidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bet":
        """Cria uma Bet a partir de um dict do Supabase."""
        from datetime import date as date_type
        target_date = None
        if data.get("target_date"):
            if isinstance(data["target_date"], str):
                target_date = date_type.fromisoformat(data["target_date"])
            else:
                target_date = data["target_date"]

        return cls(
            id=data.get("id"),
            competitor_id=data.get("competitor_id"),
            round_id=data.get("round_id"),
            target_date=target_date,
            submitted_at=data.get("submitted_at"),
            stake_value=float(data.get("stake_value", 0)),
            total_odd=float(data.get("total_odd", 1.5)),
            combined_count=int(data.get("combined_count", 1)),
            status=data.get("status", "draft"),
            deadline_at=data.get("deadline_at"),
            ocr_confidence=float(data["ocr_confidence"]) if data.get("ocr_confidence") is not None else None,
            notes=data.get("notes"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
