"""
agents/validador_regras.py — AgentValidadorRegras
Verifica regras de negócio antes da persistência final da aposta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from config.settings import MAX_BETS_PER_DAY, MIN_ODD, MAX_COMBINED, MIN_OCR_CONFIDENCE
from agents.normalizacao_aposta import NormalizedBet
from repositories.bet_repository import BetRepository
from utils.datetime_utils import is_deadline_passed


@dataclass
class ValidationResult:
    """Resultado da validação das regras de negócio."""
    status: str = "approved"   # approved | rejected | review
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"

    @property
    def needs_review(self) -> bool:
        return self.status == "review"


class AgentValidadorRegras:
    """
    Agente validador das regras de negócio para apostas normalizadas.
    """

    def validate(
        self,
        normalized_bet: NormalizedBet,
        competitor_id: str,
        form_data: Optional[dict] = None,
        existing_bet_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Executa todas as validações de regras de negócio.

        Args:
            normalized_bet: Dados normalizados da aposta.
            competitor_id: ID do competidor.
            form_data: Dados originais informados no formulário (para comparação).
            existing_bet_id: ID da aposta atual em processamento a ser excluído da contagem diária.

        Returns:
            ValidationResult com status e lista de erros/avisos.
        """
        result = ValidationResult()
        form = form_data or {}

        # --- 1. Prazo de envio ---
        target_date = normalized_bet.target_date or form.get("target_date")
        if target_date and is_deadline_passed(target_date):
            result.errors.append(
                f"Prazo de envio expirado para {target_date.strftime('%d/%m/%Y')}."
            )

        # --- 2. Limite diário ---
        if target_date and competitor_id:
            bets_today = BetRepository.count_bets_today(competitor_id, target_date, exclude_bet_id=existing_bet_id)
            if bets_today >= MAX_BETS_PER_DAY:
                result.errors.append(
                    f"Limite diário atingido: {bets_today}/{MAX_BETS_PER_DAY} apostas para essa data."
                )

        # --- 3. Seleções ---
        selections = normalized_bet.selections
        if not selections:
            result.warnings.append("OCR: Nenhuma seleção detectada na imagem. Enviado para revisão.")
        elif len(selections) > MAX_COMBINED:
            result.warnings.append(
                f"OCR: Número de seleções ({len(selections)}) excede o limite de {MAX_COMBINED}. Enviado para revisão."
            )



        # --- 5. Odd total ---
        if normalized_bet.total_odd is not None and normalized_bet.total_odd < MIN_ODD:
            result.warnings.append(
                f"OCR: Odd total {normalized_bet.total_odd:.2f} < mínimo {MIN_ODD:.2f}. Enviado para revisão."
            )



        # --- 7. Confiança da IA ---
        if normalized_bet.ocr_confidence < MIN_OCR_CONFIDENCE:
            result.warnings.append(
                f"Confiança da leitura ({normalized_bet.ocr_confidence:.0%}) abaixo do mínimo "
                f"({MIN_OCR_CONFIDENCE:.0%}). Aposta enviada para revisão manual."
            )

        # --- 8. Consistência imagem × formulário ---
        self._check_consistency(normalized_bet, form, result)

        # --- Determina status final ---
        if result.errors:
            result.status = "rejected"
        elif result.warnings:
            # Tem avisos mas sem erros críticos = revisão manual
            result.status = "review"
        else:
            result.status = "approved"

        return result

    def _check_consistency(
        self,
        normalized_bet: NormalizedBet,
        form_data: dict,
        result: ValidationResult,
    ) -> None:
        """
        Verifica consistência entre os dados da imagem e os dados informados no formulário.
        Gera warnings (não rejeita automaticamente) para revisão humana.
        """
        # Compara stake_value se ambos disponíveis
        form_stake = form_data.get("stake_value")
        img_stake = normalized_bet.stake_value
        if form_stake and img_stake:
            diff = abs(float(form_stake) - float(img_stake))
            if diff > 0.01:  # tolerância de R$ 0,01
                result.warnings.append(
                    f"Inconsistência: valor informado R$ {float(form_stake):.2f} ≠ "
                    f"valor na imagem R$ {float(img_stake):.2f}."
                )

        # Avisa sobre warnings de normalização
        for warning in normalized_bet.normalization_warnings:
            result.warnings.append(f"OCR: {warning}")
