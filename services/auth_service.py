"""
services/auth_service.py — Autenticação e autorização via Supabase Auth.
"""

from __future__ import annotations

import streamlit as st
from typing import Optional

from config.supabase_client import get_client
from repositories.competitor_repository import CompetitorRepository
from models.competitor import Profile, Competitor


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

    @staticmethod
    def populate_session(auth_data: dict) -> None:
        """
        Preenche o st.session_state com os dados de autenticação.
        Deve ser chamado após login bem-sucedido.
        """
        profile: Profile = auth_data["profile"]
        competitor: Optional[Competitor] = auth_data.get("competitor")

        st.session_state.authenticated = True
        st.session_state.user_id = auth_data["user_id"]
        st.session_state.user_email = auth_data["email"]
        st.session_state.user_role = profile.role
        st.session_state.profile_id = profile.id
        st.session_state.full_name = profile.full_name
        st.session_state.supabase_session = auth_data["session"]

        if competitor:
            st.session_state.competitor_id = competitor.id
        else:
            st.session_state.competitor_id = None

    @staticmethod
    def require_authenticated() -> None:
        """Bloqueia execução se o usuário não estiver autenticado."""
        if not st.session_state.get("authenticated", False):
            st.error("⛔ Você precisa estar autenticado para acessar esta página.")
            st.stop()

    @staticmethod
    def require_admin() -> None:
        """Bloqueia execução se o usuário não for administrador."""
        AuthService.require_authenticated()
        if st.session_state.get("user_role") != "admin":
            st.error("⛔ Acesso restrito a administradores.")
            st.stop()

    @staticmethod
    def require_competitor() -> None:
        """Bloqueia execução se o usuário não tiver um competitor_id."""
        AuthService.require_authenticated()
        if not st.session_state.get("competitor_id"):
            st.error("⛔ Seu perfil de competidor não foi encontrado. Contate o administrador.")
            st.stop()
