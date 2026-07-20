"""
backend/routers/competitors.py — Ranking geral e gestão de competidores.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.auditoria import AgentAuditoria
from backend.security import get_current_profile, require_admin
from config.supabase_client import get_admin_client
from models.competitor import Competitor, Profile
from repositories.bet_repository import BetRepository
from repositories.competitor_repository import CompetitorRepository
from services.round_service import RoundService

router = APIRouter()


@router.get("")
def list_competitors(profile: Profile = Depends(get_current_profile)):
    """Ranking geral: competidores enriquecidos com acertos e apostas da rodada ativa."""
    competitors = CompetitorRepository.get_all_competitors()

    win_counts: dict[str, int] = {}
    try:
        client = get_admin_client()
        result_wins = (
            client.table("settlements")
            .select("outcome, bets(competitor_id)")
            .eq("outcome", "win")
            .execute()
        )
        for row in result_wins.data or []:
            bet_info = row.get("bets")
            if bet_info:
                comp_id = bet_info.get("competitor_id")
                win_counts[comp_id] = win_counts.get(comp_id, 0) + 1
    except Exception:
        pass

    active_round = RoundService.get_active_round()

    payload = []
    for c in competitors:
        c.winning_bets = win_counts.get(c.id, 0)
        round_bets_count = None
        if active_round:
            bets = BetRepository.get_bets_by_competitor(c.id, limit=50)
            round_bets_count = len([b for b in bets if b.round_id == active_round.id])
        payload.append({
            "id": c.id,
            "display_name": c.display_name,
            "status": c.status,
            "points": c.points,
            "winning_bets": c.winning_bets,
            "round_bets_count": round_bets_count,
        })

    payload.sort(key=lambda x: (x["winning_bets"], x["points"]), reverse=True)
    return payload


class StatusUpdate(BaseModel):
    status: str


@router.patch("/{competitor_id}/status")
def update_status(competitor_id: str, payload: StatusUpdate, profile: Profile = Depends(require_admin)):
    if payload.status not in ("active", "inactive", "suspended"):
        raise HTTPException(status_code=400, detail="Status inválido.")
    ok = CompetitorRepository.update_competitor_status(competitor_id, payload.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Competidor não encontrado.")
    return {"ok": True}


class CompetitorCreate(BaseModel):
    full_name: str
    display_name: str | None = None


@router.post("")
def create_competitor(payload: CompetitorCreate, profile: Profile = Depends(require_admin)):
    if not payload.full_name.strip():
        raise HTTPException(status_code=400, detail="Nome completo é obrigatório.")

    final_display = payload.display_name or payload.full_name
    fake_email = f"competidor_{uuid.uuid4().hex[:8]}@n1.local"

    try:
        admin_client = get_admin_client()
        auth_res = admin_client.auth.admin.create_user({
            "email": fake_email,
            "password": uuid.uuid4().hex,
            "email_confirm": True,
        })
        if not auth_res or not auth_res.user:
            raise Exception("Falha ao criar credenciais no Supabase Auth.")
        auth_user_id = auth_res.user.id

        new_profile = Profile(
            auth_user_id=auth_user_id,
            full_name=payload.full_name,
            email=fake_email,
            role="competidor",
        )
        new_profile = CompetitorRepository.create_profile(new_profile)

        competitor = Competitor(profile_id=new_profile.id, display_name=final_display)
        competitor = CompetitorRepository.create_competitor(competitor)

        AgentAuditoria.log(
            "COMPETITOR_CREATED",
            entity_name="competitors",
            entity_id=competitor.id,
            payload={"display_name": competitor.display_name, "email": fake_email},
        )
        return {"id": competitor.id, "display_name": competitor.display_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao cadastrar competidor: {e}")
