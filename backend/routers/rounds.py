"""
backend/routers/rounds.py — Ciclo de vida das rodadas semanais.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agents.auditoria import AgentAuditoria
from agents.ranking import AgentRanking
from backend.security import get_current_profile, require_admin
from models.competitor import Profile
from repositories.competitor_repository import CompetitorRepository
from repositories.round_repository import RoundRepository
from services.ranking_service import RankingService
from services.round_service import RoundService

router = APIRouter()


@router.get("")
def list_rounds(limit: int = 50, profile: Profile = Depends(get_current_profile)):
    RoundService.check_and_auto_close()
    rounds = RoundRepository.get_all_rounds(limit=limit)
    active = RoundRepository.get_active_round()
    return {
        "rounds": rounds,
        "active_round_id": active.id if active else None,
    }


@router.get("/active")
def active_round(profile: Profile = Depends(get_current_profile)):
    RoundService.check_and_auto_close()
    return RoundService.get_active_round()


@router.get("/{round_id}/ranking")
def round_ranking(round_id: str, profile: Profile = Depends(get_current_profile)):
    return RankingService.compute_weekly_ranking(round_id)


@router.post("")
def create_round(profile: Profile = Depends(require_admin)):
    return RoundService.ensure_active_round()


@router.post("/{round_id}/close")
def close_round(round_id: str, profile: Profile = Depends(require_admin)):
    ok = RoundService.close_round(round_id)
    if ok:
        AgentAuditoria.log_round_closed(profile.auth_user_id, round_id)
    return {"ok": ok}


@router.post("/{round_id}/finalize")
def finalize_round(round_id: str, profile: Profile = Depends(require_admin)):
    agent_ranking = AgentRanking()
    winner_id = agent_ranking.determine_winner(round_id, profile.auth_user_id)
    RoundService.finalize_round(round_id)
    AgentAuditoria.log_round_finalized(profile.auth_user_id, round_id, winner_id)
    winner = CompetitorRepository.get_competitor_by_id(winner_id) if winner_id else None
    return {"winner_id": winner_id, "winner_name": winner.display_name if winner else None}
