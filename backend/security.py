"""
backend/security.py — Autenticação por Bearer token (Supabase JWT) para a API.

Cada request valida o token contra o Supabase Auth (get_user) e resolve o
Profile correspondente — substitui o st.session_state do Streamlit, que
guardava a sessão no processo. Aqui a sessão vive no browser (token) e é
revalidada a cada chamada.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from config.supabase_client import get_client
from models.competitor import Profile
from repositories.competitor_repository import CompetitorRepository


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação ausente.",
        )
    return authorization.split(" ", 1)[1].strip()


def get_current_profile(authorization: Optional[str] = Header(None)) -> Profile:
    """Valida o Bearer token contra o Supabase Auth e retorna o Profile associado."""
    token = _extract_token(authorization)

    try:
        response = get_client().auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )

    if not response or not response.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )

    profile = CompetitorRepository.get_profile_by_auth_id(response.user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil não encontrado. Entre em contato com o administrador.",
        )
    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sua conta está inativa. Entre em contato com o administrador.",
        )

    return profile


def require_admin(profile: Profile = Depends(get_current_profile)) -> Profile:
    """Bloqueia o acesso se o usuário autenticado não for administrador."""
    if profile.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return profile
