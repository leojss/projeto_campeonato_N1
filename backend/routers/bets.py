"""
backend/routers/bets.py — Histórico, submissão (pipeline de IA) e revisão de apostas.

O endpoint POST / reproduz fielmente o pipeline síncrono que existia em
ui/apostas.py::_process_bet_submission (validação de prazo/limite → upload →
leitura por IA → normalização → validação de regras → persistência).
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from agents.auditoria import AgentAuditoria
from agents.leitura_imagem import AgentLeituraImagem, ImageReadingResult
from agents.normalizacao_aposta import AgentNormalizacaoAposta, NormalizedBet
from agents.persistencia import AgentPersistencia
from agents.validador_regras import AgentValidadorRegras
from backend.security import get_current_profile, require_admin
from config.settings import MAX_BETS_PER_DAY, STORAGE_BUCKET
from config.supabase_client import get_admin_client
from models.bet import Bet, BetSelection
from models.competitor import Profile
from repositories.bet_repository import BetRepository
from repositories.competitor_repository import CompetitorRepository
from repositories.image_repository import ImageRepository
from services.upload_service import DeadlineError, UploadService
from utils.datetime_utils import get_upload_deadline, is_deadline_passed
from utils.file_utils import FileValidationError, validate_image_file

router = APIRouter()


def _bet_dict(bet: Bet) -> dict:
    return jsonable_encoder(bet)


@router.get("")
def list_bets(competitor_id: str | None = None, limit: int = 50, profile: Profile = Depends(get_current_profile)):
    if competitor_id:
        bets = BetRepository.get_bets_by_competitor(competitor_id, limit=limit)
    else:
        bets = BetRepository.get_all_bets(limit=limit)

    competitors = {c.id: c.display_name for c in CompetitorRepository.get_all_competitors()}
    result = []
    for bet in bets:
        bet.selections = BetRepository.get_selections_by_bet(bet.id)
        d = _bet_dict(bet)
        d["competitor_name"] = competitors.get(bet.competitor_id, "Desconhecido")
        result.append(d)
    return result


@router.get("/pending-review")
def pending_review(profile: Profile = Depends(require_admin)):
    bets = BetRepository.get_pending_review_bets()
    competitors = {c.id: c.display_name for c in CompetitorRepository.get_all_competitors()}
    result = []
    for bet in bets:
        bet.selections = BetRepository.get_selections_by_bet(bet.id)
        d = _bet_dict(bet)
        d["competitor_name"] = competitors.get(bet.competitor_id, "—")
        result.append(d)
    return result


@router.get("/{bet_id}/image")
def get_bet_image(bet_id: str, profile: Profile = Depends(get_current_profile)):
    bet = BetRepository.get_bet_by_id(bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada.")

    if profile.role != "admin":
        comp = CompetitorRepository.get_competitor_by_profile(profile.id)
        if not comp or comp.id != bet.competitor_id:
            raise HTTPException(status_code=403, detail="Acesso não autorizado a esta imagem.")

    img_record = ImageRepository.get_image_by_bet(bet_id)
    if not img_record:
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
    client = get_admin_client()
    try:
        img_bytes = client.storage.from_(STORAGE_BUCKET).download(img_record.storage_path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao carregar imagem: {e}")
    return Response(content=img_bytes, media_type=img_record.mime_type or "image/jpeg")


class ApproveRequest(BaseModel):
    total_odd: float
    notes: str | None = None


@router.post("/{bet_id}/approve")
def approve_bet(bet_id: str, payload: ApproveRequest, profile: Profile = Depends(require_admin)):
    bet = BetRepository.get_bet_by_id(bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada.")
    bet_data = {"status": "approved", "total_odd": payload.total_odd}
    if payload.notes:
        bet_data["notes"] = payload.notes
    BetRepository.update_bet(bet_id, bet_data)
    AgentAuditoria.log_manual_adjustment(
        profile.auth_user_id, bet_id, bet.status, "approved",
        payload.notes or f"Aprovado pelo admin (Odd: {payload.total_odd:.2f})",
    )
    return {"ok": True}


class RejectRequest(BaseModel):
    notes: str | None = None


@router.post("/{bet_id}/reject")
def reject_bet(bet_id: str, payload: RejectRequest, profile: Profile = Depends(require_admin)):
    bet = BetRepository.get_bet_by_id(bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada.")
    BetRepository.update_bet_status(bet_id, "rejected", payload.notes)
    AgentAuditoria.log_manual_adjustment(
        profile.auth_user_id, bet_id, bet.status, "rejected", payload.notes or "Rejeitado pelo admin"
    )
    return {"ok": True}


class BetUpdatePayload(BaseModel):
    stake_value: float | None = None
    total_odd: float | None = None
    status: str | None = None
    notes: str | None = None
    target_date: str | None = None


@router.patch("/{bet_id}")
def update_bet(bet_id: str, payload: BetUpdatePayload, profile: Profile = Depends(get_current_profile)):
    bet = BetRepository.get_bet_by_id(bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada.")

    if profile.role != "admin":
        comp = CompetitorRepository.get_competitor_by_profile(profile.id)
        if not comp or comp.id != bet.competitor_id:
            raise HTTPException(status_code=403, detail="Você só pode alterar suas próprias apostas.")
        if bet.status == "settled":
            raise HTTPException(status_code=400, detail="Não é possível alterar uma aposta já liquidada.")

    update_data = {}
    if payload.stake_value is not None:
        update_data["stake_value"] = payload.stake_value
    if payload.total_odd is not None:
        update_data["total_odd"] = payload.total_odd
    if payload.status is not None:
        if profile.role != "admin" and payload.status not in ["draft", "processing"]:
            raise HTTPException(status_code=403, detail="Somente administradores podem alterar o status de aprovação/liquidação.")
        update_data["status"] = payload.status
    if payload.notes is not None:
        update_data["notes"] = payload.notes
    if payload.target_date is not None:
        update_data["target_date"] = payload.target_date

    if not update_data:
        return {"ok": True, "message": "Nenhum campo para atualizar."}

    ok = BetRepository.update_bet(bet_id, update_data)
    if ok:
        AgentAuditoria.log(
            "BET_UPDATED",
            actor_id=profile.auth_user_id,
            entity_name="bets",
            entity_id=bet_id,
            payload=update_data,
        )
    return {"ok": ok}


@router.delete("/{bet_id}")
def delete_bet(bet_id: str, profile: Profile = Depends(get_current_profile)):
    bet = BetRepository.get_bet_by_id(bet_id)
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada.")

    if profile.role != "admin":
        comp = CompetitorRepository.get_competitor_by_profile(profile.id)
        if not comp or comp.id != bet.competitor_id:
            raise HTTPException(status_code=403, detail="Você só pode excluir suas próprias apostas.")

    if bet.status == "settled":
        raise HTTPException(status_code=400, detail="Não é possível excluir uma aposta já liquidada.")

    ok = BetRepository.delete_bet(bet_id)
    if ok:
        AgentAuditoria.log(
            "BET_DELETED",
            actor_id=profile.auth_user_id,
            entity_name="bets",
            entity_id=bet_id,
            payload={"reason": f"Excluído por {profile.full_name}", "target_date": str(bet.target_date)},
        )
    return {"ok": ok}


@router.post("")
def create_bet(
    competitor_id: str = Form(...),
    round_id: str = Form(...),
    target_date: str = Form(...),
    force_submission: bool = Form(False),
    file: UploadFile = File(...),
    profile: Profile = Depends(get_current_profile),
):
    """Reproduz o pipeline completo: validação → upload → OCR IA → normalização → validação → persistência."""
    actor_id = profile.auth_user_id
    t_date = date_type.fromisoformat(target_date)

    if profile.role != "admin":
        comp = CompetitorRepository.get_competitor_by_profile(profile.id)
        if not comp or comp.id != competitor_id:
            raise HTTPException(
                status_code=403,
                detail="Você só pode enviar apostas para o seu próprio perfil de competidor.",
            )
        if force_submission:
            raise HTTPException(
                status_code=403,
                detail="Somente administradores podem forçar a submissão fora do prazo.",
            )

    if is_deadline_passed(t_date) and not force_submission:
        AgentAuditoria.log_deadline_exceeded(actor_id, str(t_date))
        raise HTTPException(
            status_code=400,
            detail=f"Prazo expirado para apostas na data {t_date.strftime('%d/%m/%Y')}. "
                   "Ative o cadastro forçado para prosseguir.",
        )

    bets_today = BetRepository.count_bets_today(competitor_id, t_date)
    if bets_today >= MAX_BETS_PER_DAY:
        AgentAuditoria.log_limit_exceeded(actor_id, str(t_date), bets_today)
        raise HTTPException(
            status_code=400,
            detail=f"Limite diário de {MAX_BETS_PER_DAY} apostas atingido para o jogador selecionado nessa data.",
        )

    file_content = file.file.read()
    filename = file.filename or "comprovante.jpg"
    mime_type = file.content_type or "image/jpeg"

    try:
        if not force_submission:
            UploadService.validate_upload(file_content, filename, mime_type, t_date)
        else:
            validate_image_file(file_content, filename, mime_type)
    except DeadlineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    temp_bet = Bet(
        competitor_id=competitor_id,
        round_id=round_id,
        target_date=t_date,
        stake_value=1.0,
        total_odd=1.5,
        combined_count=1,
        status="processing",
        deadline_at=get_upload_deadline(t_date),
    )
    temp_bet = BetRepository.create_bet(temp_bet)

    try:
        storage_path = UploadService.upload_image(file_content, filename, mime_type, competitor_id, temp_bet.id)
        AgentAuditoria.log_upload_completed(actor_id, temp_bet.id, storage_path)
    except Exception as e:
        BetRepository.update_bet_status(temp_bet.id, "rejected", f"Falha no upload: {e}")
        raise HTTPException(status_code=502, detail=f"Falha ao enviar imagem para o storage: {e}")

    try:
        agent_leitura = AgentLeituraImagem()
        reading_result = agent_leitura.read_image(file_content, {"target_date": str(t_date)})
        AgentAuditoria.log_ocr_processed(temp_bet.id, reading_result.confidence_score, "extracted")
    except Exception as e:
        reading_result = ImageReadingResult(error=str(e), needs_review=True)
        AgentAuditoria.log_ocr_failed(temp_bet.id, str(e))

    agent_norm = AgentNormalizacaoAposta()
    normalized = agent_norm.normalize(reading_result, metadata={"target_date": t_date})

    agent_valid = AgentValidadorRegras()
    validation = agent_valid.validate(
        normalized,
        competitor_id,
        form_data={"target_date": t_date},
        existing_bet_id=temp_bet.id,
        force_submission=force_submission,
    )

    agent_persist = AgentPersistencia()
    result = agent_persist.persist(
        normalized_bet=normalized,
        validation_result=validation,
        image_reading=reading_result,
        storage_path=storage_path,
        original_filename=filename,
        mime_type=mime_type,
        file_size=len(file_content),
        competitor_id=competitor_id,
        round_id=round_id,
        actor_id=actor_id,
        form_data={"target_date": t_date},
        existing_bet_id=temp_bet.id,
    )

    return {
        "status": result.status,
        "message": result.message,
        "bet_id": result.bet_id,
        "extracted": {
            "total_odd": normalized.total_odd,
            "aposta_descricao": normalized.aposta_descricao,
            "confidence": reading_result.confidence_score,
        },
        "warnings": validation.warnings,
        "errors": validation.errors,
    }


class ManualBetRequest(BaseModel):
    competitor_id: str
    round_id: str
    target_date: str
    total_odd: float = Field(..., gt=0)
    aposta_descricao: str
    force_submission: bool = False


@router.post("/manual")
def create_bet_manual(payload: ManualBetRequest, profile: Profile = Depends(get_current_profile)):
    """Registra uma aposta digitada manualmente (sem comprovante de imagem)."""
    actor_id = profile.auth_user_id
    t_date = date_type.fromisoformat(payload.target_date)

    if profile.role != "admin":
        comp = CompetitorRepository.get_competitor_by_profile(profile.id)
        if not comp or comp.id != payload.competitor_id:
            raise HTTPException(
                status_code=403,
                detail="Você só pode enviar apostas para o seu próprio perfil de competidor.",
            )
        if payload.force_submission:
            raise HTTPException(
                status_code=403,
                detail="Somente administradores podem forçar a submissão fora do prazo.",
            )

    descricao = payload.aposta_descricao.strip()
    if not descricao:
        raise HTTPException(status_code=400, detail="Descreva a aposta.")

    normalized = NormalizedBet(
        target_date=t_date,
        total_odd=payload.total_odd,
        aposta_descricao=descricao,
        ocr_confidence=1.0,
    )
    normalized.selections = [BetSelection(
        selection_order=1,
        description=descricao,
        odd=payload.total_odd,
        result_status="pending",
    )]

    agent_valid = AgentValidadorRegras()
    validation = agent_valid.validate(
        normalized,
        payload.competitor_id,
        form_data={"target_date": t_date},
        force_submission=payload.force_submission,
    )

    agent_persist = AgentPersistencia()
    result = agent_persist.persist_manual(
        normalized_bet=normalized,
        validation_result=validation,
        competitor_id=payload.competitor_id,
        round_id=payload.round_id,
        actor_id=actor_id,
        form_data={"target_date": t_date},
    )

    return {
        "status": result.status,
        "message": result.message,
        "bet_id": result.bet_id,
        "warnings": validation.warnings,
        "errors": validation.errors,
    }
