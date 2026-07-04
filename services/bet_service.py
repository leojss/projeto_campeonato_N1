"""
services/bet_service.py — Orquestração das regras de negócio de apostas.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from config.settings import MAX_BETS_PER_DAY, MIN_ODD, MAX_COMBINED
from models.bet import Bet, BetSelection
from repositories.bet_repository import BetRepository
from utils.datetime_utils import get_upload_deadline, is_deadline_passed


class BetValidationError(Exception):
    """Erro de violação de regra de negócio na aposta."""
    pass


class BetService:
    """Serviço de domínio para apostas."""

    @staticmethod
    def calculate_total_odd(selections: list[BetSelection]) -> float:
        """
        Calcula a odd total como produto das odds das seleções.

        Args:
            selections: Lista de seleções (máx 3).

        Returns:
            Odd total (produto).
        """
        if not selections:
            raise BetValidationError("A aposta deve ter pelo menos uma seleção.")
        result = 1.0
        for sel in selections:
            result *= sel.odd
        return round(result, 4)

    @staticmethod
    def calculate_gross_return(stake_value: float, total_odd: float) -> float:
        """Retorno bruto se a aposta vencer: stake × total_odd."""
        return round(stake_value * total_odd, 2)

    @staticmethod
    def calculate_net_profit(gross_return: Optional[float], stake_value: float, won: bool) -> float:
        """
        Lucro líquido da aposta.

        - Se ganhou: gross_return - stake_value
        - Se perdeu: -stake_value
        """
        if won and gross_return is not None:
            return round(gross_return - stake_value, 2)
        return round(-stake_value, 2)

    @staticmethod
    def validate_bet_rules(
        competitor_id: str,
        target_date: date,
        selections: list[BetSelection],
        stake_value: float,
    ) -> None:
        """
        Valida todas as regras de negócio ANTES de criar a aposta.

        Raises:
            BetValidationError: Se alguma regra for violada.
        """
        # 1. Prazo de envio
        if is_deadline_passed(target_date):
            deadline = get_upload_deadline(target_date)
            raise BetValidationError(
                f"Prazo expirado para apostas em {target_date.strftime('%d/%m/%Y')}. "
                f"O prazo era até {deadline.strftime('%d/%m/%Y às %H:%M')}."
            )

        # 2. Limite diário
        bets_today = BetRepository.count_bets_today(competitor_id, target_date)
        if bets_today >= MAX_BETS_PER_DAY:
            raise BetValidationError(
                f"Limite diário atingido. Você já possui {bets_today} aposta(s) "
                f"para {target_date.strftime('%d/%m/%Y')} (máximo: {MAX_BETS_PER_DAY})."
            )

        # 3. Número de seleções (combinadas)
        if not selections:
            raise BetValidationError("A aposta deve ter pelo menos 1 seleção.")
        if len(selections) > MAX_COMBINED:
            raise BetValidationError(
                f"Número de seleções excede o limite. "
                f"Máximo: {MAX_COMBINED} seleção(ões), informado: {len(selections)}."
            )

        # 4. Odd total mínima (produto das seleções)
        total_odd = 1.0
        for sel in selections:
            total_odd *= sel.odd
        total_odd = round(total_odd, 4)
        if total_odd < MIN_ODD:
            raise BetValidationError(
                f"A odd total calculada ({total_odd:.2f}) é inferior ao mínimo permitido ({MIN_ODD:.2f})."
            )

        # 5. Valor apostado
        if stake_value <= 0:
            raise BetValidationError("O valor da aposta deve ser maior que zero.")

    @staticmethod
    def build_bet(
        competitor_id: str,
        round_id: str,
        target_date: date,
        stake_value: float,
        selections: list[BetSelection],
    ) -> Bet:
        """
        Constrói o objeto Bet com todos os campos calculados.

        Returns:
            Bet pronta para persistência.
        """
        total_odd = BetService.calculate_total_odd(selections)
        deadline_at = get_upload_deadline(target_date)

        bet = Bet(
            competitor_id=competitor_id,
            round_id=round_id,
            target_date=target_date,
            stake_value=stake_value,
            total_odd=total_odd,
            combined_count=len(selections),
            status="submitted",
            deadline_at=deadline_at,
        )

        for i, sel in enumerate(selections, 1):
            sel.selection_order = i

        bet.selections = selections
        return bet
