"""
models/competitor.py — Modelos de domínio para competidores e perfis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Profile:
    """Perfil do usuário autenticado via Supabase Auth."""
    id: Optional[str] = None
    auth_user_id: Optional[str] = None
    full_name: str = ""
    email: str = ""
    role: str = "competidor"        # competidor | admin
    is_active: bool = True
    points: float = 100.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict:
        return {
            "auth_user_id": self.auth_user_id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "points": self.points,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            id=data.get("id"),
            auth_user_id=data.get("auth_user_id"),
            full_name=data.get("full_name", ""),
            email=data.get("email", ""),
            role=data.get("role", "competidor"),
            is_active=data.get("is_active", True),
            points=float(data.get("points", 100.0)),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Competitor:
    """Cadastro lógico do competidor na competição."""
    id: Optional[str] = None
    profile_id: Optional[str] = None
    display_name: str = ""
    avatar_url: Optional[str] = None
    status: str = "active"          # active | inactive | suspended
    created_at: Optional[datetime] = None
    points: float = 100.0

    # Dados enriquecidos (calculados dinamicamente)
    total_bets: int = 0
    winning_bets: int = 0
    net_profit: float = 0.0
    win_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Competitor":
        # Tenta ler points se vier aninhado de profiles
        points_val = 100.0
        if data.get("profiles") and isinstance(data["profiles"], dict):
            points_val = float(data["profiles"].get("points", 100.0))
        elif data.get("points") is not None:
            points_val = float(data.get("points"))

        return cls(
            id=data.get("id"),
            profile_id=data.get("profile_id"),
            display_name=data.get("display_name", ""),
            avatar_url=data.get("avatar_url"),
            status=data.get("status", "active"),
            created_at=data.get("created_at"),
            points=points_val,
        )
