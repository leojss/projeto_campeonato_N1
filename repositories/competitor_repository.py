"""
repositories/competitor_repository.py — Acesso ao banco para competidores e perfis.
"""

from __future__ import annotations

from typing import Optional

from config.supabase_client import get_admin_client, get_client
from models.competitor import Competitor, Profile


class CompetitorRepository:
    """Repositório de competidores."""

    COMPETITORS_TABLE = "competitors"
    PROFILES_TABLE = "profiles"

    @staticmethod
    def get_all_competitors() -> list[Competitor]:
        """Retorna todos os competidores com join no profile (com fallback resiliente para a coluna points)."""
        client = get_admin_client()
        try:
            # Tenta selecionar com points
            result = (
                client.table(CompetitorRepository.COMPETITORS_TABLE)
                .select("*, profiles(full_name, email, role, points)")
                .order("display_name")
                .execute()
            )
        except Exception as e:
            # Se a coluna points não existir no banco do Supabase, executa fallback sem ela
            if "points" in str(e) or "42703" in str(e):
                result = (
                    client.table(CompetitorRepository.COMPETITORS_TABLE)
                    .select("*, profiles(full_name, email, role)")
                    .order("display_name")
                    .execute()
                )
            else:
                raise e

        competitors = []
        for row in result.data:
            c = Competitor.from_dict(row)
            if row.get("profiles"):
                c.display_name = c.display_name or row["profiles"].get("full_name", "")
            competitors.append(c)
        return competitors

    @staticmethod
    def get_competitor_by_profile(profile_id: str) -> Optional[Competitor]:
        """Retorna o competidor associado a um profile_id."""
        client = get_admin_client()
        result = (
            client.table(CompetitorRepository.COMPETITORS_TABLE)
            .select("*")
            .eq("profile_id", profile_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Competitor.from_dict(result.data[0])

    @staticmethod
    def get_competitor_by_id(competitor_id: str) -> Optional[Competitor]:
        """Retorna um competidor pelo ID."""
        client = get_admin_client()
        result = (
            client.table(CompetitorRepository.COMPETITORS_TABLE)
            .select("*")
            .eq("id", competitor_id)
            .single()
            .execute()
        )
        if result.data:
            return Competitor.from_dict(result.data)
        return None

    @staticmethod
    def create_competitor(competitor: Competitor) -> Competitor:
        """Cria um novo competidor."""
        client = get_admin_client()
        result = (
            client.table(CompetitorRepository.COMPETITORS_TABLE)
            .insert(competitor.to_dict())
            .execute()
        )
        data = result.data[0]
        competitor.id = data["id"]
        return competitor

    @staticmethod
    def update_competitor_status(competitor_id: str, status: str) -> bool:
        """Ativa, desativa ou suspende um competidor."""
        client = get_admin_client()
        result = (
            client.table(CompetitorRepository.COMPETITORS_TABLE)
            .update({"status": status})
            .eq("id", competitor_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def get_profile_by_auth_id(auth_user_id: str) -> Optional[Profile]:
        """Retorna o perfil de um usuário pelo auth_user_id."""
        client = get_admin_client()
        result = (
            client.table(CompetitorRepository.PROFILES_TABLE)
            .select("*")
            .eq("auth_user_id", auth_user_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return Profile.from_dict(result.data[0])

    @staticmethod
    def create_profile(profile: Profile) -> Profile:
        """Cria um perfil para um usuário recém-cadastrado."""
        client = get_admin_client()
        result = (
            client.table(CompetitorRepository.PROFILES_TABLE)
            .insert(profile.to_dict())
            .execute()
        )
        data = result.data[0]
        profile.id = data["id"]
        return profile
