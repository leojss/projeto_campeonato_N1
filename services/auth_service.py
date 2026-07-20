"""
services/auth_service.py — Autenticação e autorização via Supabase Auth.
"""

from __future__ import annotations

from typing import Optional

from config.supabase_client import get_client
from repositories.competitor_repository import CompetitorRepository
from models.competitor import Competitor


class AuthError(Exception):
    """Erro de autenticação ou autorização."""
    pass


class AuthService:
    """Serviço de autenticação integrado ao Supabase Auth."""

    @staticmethod
    def login(email: str, password: str) -> dict:
        """
        Autentica o usuário no Supabase.

        Returns:
            Dict com: user_id, email, profile, competitor (se existir)

        Raises:
            AuthError: Se as credenciais forem inválidas.
        """
        client = get_client()
        try:
            response = client.auth.sign_in_with_password({
                "email": email.strip().lower(),
                "password": password,
            })
        except Exception as e:
            raise AuthError(f"Falha no login: {str(e)}")

        if not response.user:
            raise AuthError("Credenciais inválidas. Verifique seu e-mail e senha.")

        user = response.user
        session = response.session

        # Busca o perfil no banco
        profile = CompetitorRepository.get_profile_by_auth_id(user.id)
        if not profile:
            raise AuthError(
                "Perfil não encontrado. Entre em contato com o administrador."
            )

        if not profile.is_active:
            raise AuthError("Sua conta está inativa. Entre em contato com o administrador.")

        # Busca o competitor (se for um competidor)
        competitor: Optional[Competitor] = None
        if profile.role == "competidor":
            competitor = CompetitorRepository.get_competitor_by_profile(profile.id)

        return {
            "user_id": user.id,
            "email": user.email,
            "session": session,
            "profile": profile,
            "competitor": competitor,
        }

    @staticmethod
    def logout() -> None:
        """Encerra a sessão no Supabase."""
        try:
            client = get_client()
            client.auth.sign_out()
        except Exception:
            pass  # Falha silenciosa no logout
