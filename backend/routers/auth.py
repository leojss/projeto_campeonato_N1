"""
backend/routers/auth.py — Login/logout via Supabase Auth.

Reaproveita AuthService.login integralmente; a única mudança é que a sessão
resultante (access_token) é devolvida ao browser em vez de guardada em
st.session_state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from agents.auditoria import AgentAuditoria
from backend.security import get_current_profile
from models.competitor import Profile
from repositories.competitor_repository import CompetitorRepository
from services.auth_service import AuthError, AuthService

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    try:
        auth_data = AuthService.login(payload.email, payload.password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    profile: Profile = auth_data["profile"]

    AgentAuditoria.log_login(actor_id=auth_data["user_id"], email=payload.email)

    comp = CompetitorRepository.get_competitor_by_profile(profile.id)
    session = auth_data["session"]
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user": {
            "id": auth_data["user_id"],
            "email": auth_data["email"],
            "full_name": profile.full_name,
            "role": profile.role,
            "profile_id": profile.id,
            "competitor_id": comp.id if comp else None,
        },
    }


@router.post("/logout")
def logout(profile: Profile = Depends(get_current_profile)):
    AuthService.logout()
    AgentAuditoria.log_logout(profile.auth_user_id)
    return {"ok": True}


@router.get("/me")
def me(profile: Profile = Depends(get_current_profile)):
    return profile
