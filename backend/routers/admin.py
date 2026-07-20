"""
backend/routers/admin.py — Liquidação de apostas e logs de auditoria.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from agents.auditoria import AgentAuditoria
from backend.security import require_admin
from models.audit import AuditAction
from models.bet import Settlement
from models.competitor import Profile
from repositories.audit_repository import AuditRepository
from repositories.bet_repository import BetRepository
from repositories.competitor_repository import CompetitorRepository
from repositories.round_repository import RoundRepository
from repositories.settlement_repository import SettlementRepository
from services.settlement_service import SettlementService

router = APIRouter()


@router.get("/approved-bets")
def approved_bets(round_id: str | None = None, profile: Profile = Depends(require_admin)):
    active_round = RoundRepository.get_round_by_id(round_id) if round_id else RoundRepository.get_active_round()
    if not active_round:
        return []
    bets = [b for b in BetRepository.get_bets_by_round(active_round.id) if b.status == "approved"]
    competitors = {c.id: c.display_name for c in CompetitorRepository.get_all_competitors()}
    result = []
    for bet in bets:
        bet.selections = BetRepository.get_selections_by_bet(bet.id)
        d = jsonable_encoder(bet)
        d["competitor_name"] = competitors.get(bet.competitor_id, "—")
        result.append(d)
    return result


class SettleRequest(BaseModel):
    bet_id: str
    outcome: str


@router.post("/settlements")
def settle_bet(payload: SettleRequest, profile: Profile = Depends(require_admin)):
    bet = BetRepository.get_bet_by_id(payload.bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada.")
    if payload.outcome not in ("win", "loss", "void"):
        raise HTTPException(status_code=400, detail="Resultado inválido.")

    gross_return = bet.stake_value * bet.total_odd
    net_profit = (
        (gross_return - bet.stake_value) if payload.outcome == "win"
        else (-bet.stake_value) if payload.outcome == "loss"
        else 0.0
    )

    settlement = Settlement(
        bet_id=bet.id,
        outcome=payload.outcome,
        gross_return=gross_return if payload.outcome == "win" else None,
        net_profit=net_profit,
    )
    SettlementRepository.upsert_settlement(settlement)
    BetRepository.update_bet_status(bet.id, "settled")
    AgentAuditoria.log(
        AuditAction.BET_APPROVED,
        actor_id=profile.auth_user_id,
        entity_name="settlements",
        entity_id=bet.id,
        payload={"outcome": payload.outcome, "net_profit": net_profit},
    )
    return {"ok": True, "net_profit": net_profit}


@router.post("/settlements/auto-run")
def auto_settlement(profile: Profile = Depends(require_admin)):
    try:
        results = SettlementService.run_auto_settlement()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    quota_error = any("429" in str(m) or "RESOURCE_EXHAUSTED" in str(m) for m in results["logs"])
    results["quota_warning"] = bool(quota_error and results["selections_resolved"] == 0)
    return results


@router.get("/audit-logs")
def audit_logs(action: str | None = None, limit: int = 100, profile: Profile = Depends(require_admin)):
    if action and action != "Todas":
        logs = AuditRepository.get_logs_by_action(action, limit=limit)
    else:
        logs = AuditRepository.get_recent_logs(limit=limit)
    return logs
