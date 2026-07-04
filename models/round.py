"""
models/round.py — Modelos de domínio para rodadas e competições.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional


@dataclass
class Competition:
    """Competição principal (uma ativa por vez)."""
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    status: str = "active"          # active | paused | finished
    timezone: str = "America/Sao_Paulo"
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Competition":
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description"),
            status=data.get("status", "active"),
            timezone=data.get("timezone", "America/Sao_Paulo"),
            created_at=data.get("created_at"),
        )


@dataclass
class Round:
    """Rodada semanal: domingo → sábado."""
    id: Optional[str] = None
    competition_id: Optional[str] = None
    week_number: int = 0
    start_date: Optional[date] = None       # domingo
    end_date: Optional[date] = None         # sábado
    status: str = "scheduled"              # scheduled | open | closed | finalized
    winner_competitor_id: Optional[str] = None
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def label(self) -> str:
        if self.start_date and self.end_date:
            from utils.datetime_utils import format_br_date
            return f"Semana {self.week_number} ({format_br_date(self.start_date)} – {format_br_date(self.end_date)})"
        return f"Semana {self.week_number}"

    def to_dict(self) -> dict:
        return {
            "competition_id": self.competition_id,
            "week_number": self.week_number,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Round":
        start_date = None
        end_date = None
        if data.get("start_date"):
            if isinstance(data["start_date"], str):
                start_date = date.fromisoformat(data["start_date"])
            else:
                start_date = data["start_date"]
        if data.get("end_date"):
            if isinstance(data["end_date"], str):
                end_date = date.fromisoformat(data["end_date"])
            else:
                end_date = data["end_date"]

        return cls(
            id=data.get("id"),
            competition_id=data.get("competition_id"),
            week_number=data.get("week_number", 0),
            start_date=start_date,
            end_date=end_date,
            status=data.get("status", "scheduled"),
            winner_competitor_id=data.get("winner_competitor_id"),
            created_at=data.get("created_at"),
            closed_at=data.get("closed_at"),
        )


@dataclass
class RankingEntry:
    """Entrada do ranking semanal de um competidor."""
    position: int = 0
    competitor_id: str = ""
    display_name: str = ""
    total_bets: int = 0
    winning_bets: int = 0
    net_profit: float = 0.0
    gross_return: float = 0.0
    win_rate: float = 0.0
    last_submission: Optional[datetime] = None

    @property
    def win_rate_pct(self) -> str:
        return f"{self.win_rate * 100:.1f}%"
