"""
agents/persistencia.py — AgentPersistencia
Persiste os dados validados da aposta no Supabase de forma idempotente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from models.bet import Bet, BetImage
from agents.leitura_imagem import ImageReadingResult
from agents.normalizacao_aposta import NormalizedBet
from agents.validador_regras import ValidationResult
from repositories.bet_repository import BetRepository
from repositories.image_repository import ImageRepository
from repositories.audit_repository import AuditRepository
from models.audit import AuditAction
from utils.datetime_utils import get_upload_deadline

# Stake fixo — o sistema não trata valores apostados, apenas odd e resultado.
_PLACEHOLDER_STAKE = 1.0


@dataclass
class PersistenceResult:
    """Resultado da persistência."""
    success: bool = False
    bet_id: Optional[str] = None
    image_id: Optional[str] = None
    status: str = "rejected"
    message: str = ""
    error: Optional[str] = None


class AgentPersistencia:
    """
    Agente de persistência — grava todos os dados da aposta no Supabase.

    Ordem de operações (fluxo com imagem):
    1. Criar registro da aposta (bet)
    2. Criar seleções (bet_selections)
    3. Salvar registro da imagem (bet_images)
    4. Atualizar OCR bruto
    5. Registrar auditoria

    O fluxo manual (persist_manual) pula os passos 3 e 4 — não há imagem.
    """

    def persist(
        self,
        normalized_bet: NormalizedBet,
        validation_result: ValidationResult,
        image_reading: ImageReadingResult,
        storage_path: str,
        original_filename: str,
        mime_type: str,
        file_size: int,
        competitor_id: str,
        round_id: str,
        actor_id: Optional[str] = None,
        form_data: Optional[dict] = None,
        existing_bet_id: Optional[str] = None,
    ) -> PersistenceResult:
        """
        Persiste a aposta completa no banco (criando ou atualizando), incluindo o
        registro da imagem e o resultado do OCR.

        Returns:
            PersistenceResult com bet_id, image_id e status final.
        """
        try:
            bet_id, final_status = self._save_bet(
                normalized_bet, validation_result, competitor_id, round_id,
                form_data or {}, existing_bet_id, ocr_confidence=image_reading.confidence_score,
            )

            # --- Salva registro da imagem ---
            image_record = BetImage(
                bet_id=bet_id,
                storage_path=storage_path,
                original_filename=original_filename,
                mime_type=mime_type,
                file_size=file_size,
                status="processing",
            )
            image_record = ImageRepository.save_image_record(image_record)

            # --- Atualiza OCR ---
            ocr_status = "extracted" if not image_reading.error else "failed"
            if validation_result.is_approved:
                ocr_status = "approved"
            elif validation_result.is_rejected:
                ocr_status = "rejected"

            ImageRepository.update_ocr_result(
                image_id=image_record.id,
                ocr_text=image_reading.raw_text,
                ocr_json=image_reading.ocr_json,
                confidence_score=image_reading.confidence_score,
                status=ocr_status,
            )

            self._log_audit(bet_id, actor_id, final_status, validation_result, normalized_bet,
                             ocr_confidence=image_reading.confidence_score)

            return PersistenceResult(
                success=True,
                bet_id=bet_id,
                image_id=image_record.id,
                status=final_status,
                message=self._build_message(final_status, validation_result),
            )

        except Exception as e:
            return self._persist_error(actor_id, e)

    def persist_manual(
        self,
        normalized_bet: NormalizedBet,
        validation_result: ValidationResult,
        competitor_id: str,
        round_id: str,
        actor_id: Optional[str] = None,
        form_data: Optional[dict] = None,
    ) -> PersistenceResult:
        """
        Persiste uma aposta inserida manualmente (sem comprovante de imagem).

        Returns:
            PersistenceResult com bet_id e status final (sem image_id).
        """
        try:
            bet_id, final_status = self._save_bet(
                normalized_bet, validation_result, competitor_id, round_id,
                form_data or {}, existing_bet_id=None, ocr_confidence=1.0,
            )

            self._log_audit(bet_id, actor_id, final_status, validation_result, normalized_bet,
                             ocr_confidence=1.0)

            return PersistenceResult(
                success=True,
                bet_id=bet_id,
                image_id=None,
                status=final_status,
                message=self._build_message(final_status, validation_result),
            )

        except Exception as e:
            return self._persist_error(actor_id, e)

    def _save_bet(
        self,
        normalized_bet: NormalizedBet,
        validation_result: ValidationResult,
        competitor_id: str,
        round_id: str,
        form: dict,
        existing_bet_id: Optional[str],
        ocr_confidence: float,
    ) -> tuple[str, str]:
        """Grava a aposta e suas seleções. Retorna (bet_id, status_final)."""
        target_date = normalized_bet.target_date or form.get("target_date")
        selections = normalized_bet.selections or []

        # Odd total: recalcula a partir das seleções se disponível
        if selections:
            total_odd = 1.0
            for sel in selections:
                total_odd *= sel.odd
            total_odd = round(total_odd, 4)
        else:
            total_odd = normalized_bet.total_odd or 1.50

        if total_odd < 1.50:
            total_odd = 1.50
            warning_msg = "Odd total inferior a 1.50. Definida temporariamente para 1.50 para revisão."
            if warning_msg not in validation_result.warnings:
                validation_result.warnings.append(warning_msg)
            if validation_result.status == "approved":
                validation_result.status = "review"

        deadline_at = get_upload_deadline(target_date) if target_date else None
        final_status = validation_result.status

        bet_data = {
            "competitor_id": competitor_id,
            "round_id": round_id,
            "target_date": target_date.isoformat() if target_date else None,
            "submitted_at": datetime.utcnow().isoformat(),
            "stake_value": _PLACEHOLDER_STAKE,
            "total_odd": total_odd,
            "combined_count": len(selections) if selections else 1,
            "status": final_status,
            "deadline_at": deadline_at.isoformat() if deadline_at else None,
            "ocr_confidence": ocr_confidence,
            "notes": "; ".join(validation_result.warnings) if validation_result.warnings else None,
        }

        if existing_bet_id:
            BetRepository.update_bet(existing_bet_id, bet_data)
            bet_id = existing_bet_id
        else:
            bet = Bet(
                competitor_id=competitor_id,
                round_id=round_id,
                target_date=target_date,
                submitted_at=datetime.utcnow(),
                stake_value=_PLACEHOLDER_STAKE,
                total_odd=total_odd,
                combined_count=len(selections) if selections else 1,
                status=final_status,
                deadline_at=deadline_at,
                ocr_confidence=ocr_confidence,
                notes="; ".join(validation_result.warnings) if validation_result.warnings else None,
            )
            bet = BetRepository.create_bet(bet)
            bet_id = bet.id

        if selections:
            for i, sel in enumerate(selections, 1):
                sel.bet_id = bet_id
                sel.selection_order = i
            BetRepository.create_selections(selections)

        return bet_id, final_status

    def _log_audit(
        self,
        bet_id: str,
        actor_id: Optional[str],
        final_status: str,
        validation_result: ValidationResult,
        normalized_bet: NormalizedBet,
        ocr_confidence: float,
    ) -> None:
        action = AuditAction.BET_SUBMITTED if final_status == "approved" else \
                 AuditAction.BET_REJECTED if final_status == "rejected" else \
                 AuditAction.OCR_LOW_CONFIDENCE

        AuditRepository.log_event(
            action=action,
            actor_id=actor_id,
            entity_name="bets",
            entity_id=bet_id,
            payload={
                "status": final_status,
                "ocr_confidence": ocr_confidence,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "aposta_descricao": normalized_bet.aposta_descricao,
            },
        )

    def _persist_error(self, actor_id: Optional[str], error: Exception) -> PersistenceResult:
        AuditRepository.log_event(
            action=AuditAction.BET_REJECTED,
            actor_id=actor_id,
            entity_name="bets",
            payload={"error": str(error)},
        )
        return PersistenceResult(
            success=False,
            status="rejected",
            message="Erro interno ao persistir a aposta.",
            error=str(error),
        )

    def _build_message(self, status: str, result: ValidationResult) -> str:
        """Monta mensagem de retorno para o usuário."""
        if status == "approved":
            return "✅ Aposta registrada com sucesso!"
        elif status == "review":
            warnings = "; ".join(result.warnings)
            return f"🔍 Aposta enviada para revisão manual. {warnings}"
        else:
            errors = "; ".join(result.errors)
            return f"❌ Aposta rejeitada. {errors}"
