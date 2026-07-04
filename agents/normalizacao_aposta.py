"""
agents/normalizacao_aposta.py — AgentNormalizacaoAposta
Converte a saída bruta da leitura da imagem em estrutura padronizada de aposta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from models.bet import BetSelection
from agents.leitura_imagem import ImageReadingResult


@dataclass
class NormalizedBet:
    """Aposta normalizada pronta para validação e persistência."""
    target_date: Optional[date] = None
    stake_value: Optional[float] = None
    total_odd: Optional[float] = None
    selections: list[BetSelection] = None
    bookmaker: Optional[str] = None
    observacoes: Optional[str] = None
    ocr_confidence: float = 0.0
    normalization_warnings: list[str] = None

    def __post_init__(self):
        if self.selections is None:
            self.selections = []
        if self.normalization_warnings is None:
            self.normalization_warnings = []


class AgentNormalizacaoAposta:
    """
    Agente de normalização: transforma saída do OCR em estrutura de dados limpa.
    """

    def normalize(
        self,
        reading_result: ImageReadingResult,
        metadata: Optional[dict] = None,
    ) -> NormalizedBet:
        """
        Normaliza os dados extraídos da imagem.

        Args:
            reading_result: Resultado da leitura pelo AgentLeituraImagem.
            metadata: Dados informados pelo usuário (target_date, stake_value, etc.)

        Returns:
            NormalizedBet com campos normalizados e warnings de inconsistência.
        """
        normalized = NormalizedBet(ocr_confidence=reading_result.confidence_score)
        ocr = reading_result.ocr_json or {}
        meta = metadata or {}

        # --- Data da aposta ---
        normalized.target_date = self._normalize_date(
            ocr.get("data_aposta"),
            meta.get("target_date"),
            normalized.normalization_warnings,
        )

        # --- Valor apostado ---
        normalized.stake_value = self._normalize_float(
            ocr.get("valor_apostado"),
            meta.get("stake_value"),
            "valor apostado",
            normalized.normalization_warnings,
        )

        # --- Odd total ---
        normalized.total_odd = self._normalize_odd(
            ocr.get("odd_total"),
            normalized.normalization_warnings,
        )

        # --- Seleções ---
        normalized.selections = self._normalize_selections(
            ocr.get("selecoes", []),
            normalized.normalization_warnings,
        )

        # Distribuição Geométrica de Odds: se as odds das seleções vierem nulas (ex: Bet Builder),
        # mas temos a odd total, calcula a raiz enésima para que o produto delas bata com a odd total
        if normalized.selections:
            n_selections = len(normalized.selections)
            has_missing_odds = any(sel.odd is None for sel in normalized.selections)
            
            if has_missing_odds:
                if normalized.total_odd and normalized.total_odd >= 1.0:
                    # Calcula a raiz enésima da odd total
                    nth_root_odd = round(normalized.total_odd ** (1 / n_selections), 4)
                    for sel in normalized.selections:
                        if sel.odd is None:
                            sel.odd = nth_root_odd
                else:
                    # Fallback clássico caso não tenhamos a odd total
                    for sel in normalized.selections:
                        if sel.odd is None:
                            sel.odd = 1.50
            else:
                # Garante que as odds sejam floats válidas
                for sel in normalized.selections:
                    sel.odd = float(sel.odd)

        # --- Metadados extras ---
        normalized.bookmaker = ocr.get("bookmaker")
        normalized.observacoes = ocr.get("observacoes")

        return normalized

    def _normalize_date(
        self,
        ocr_date: Optional[str],
        meta_date,
        warnings: list[str],
    ) -> Optional[date]:
        """Normaliza a data, priorizando o metadado informado pelo usuário."""
        # Prioridade: o usuário informou a data no formulário
        if meta_date:
            if isinstance(meta_date, date):
                return meta_date
            if isinstance(meta_date, str):
                try:
                    return date.fromisoformat(meta_date)
                except ValueError:
                    pass

        # Fallback: data extraída da imagem
        if ocr_date:
            try:
                return date.fromisoformat(str(ocr_date))
            except (ValueError, TypeError):
                warnings.append(f"Data extraída pelo OCR inválida: '{ocr_date}'")

        warnings.append("Data da aposta não encontrada na imagem nem nos metadados.")
        return None

    def _normalize_float(
        self,
        ocr_value,
        meta_value,
        field_name: str,
        warnings: list[str],
    ) -> Optional[float]:
        """Normaliza um valor numérico, priorizando metadado."""
        # Usa o valor do formulário se disponível
        if meta_value is not None:
            try:
                return float(meta_value)
            except (ValueError, TypeError):
                pass

        # Fallback: valor da imagem
        if ocr_value is not None:
            try:
                return float(str(ocr_value).replace(",", "."))
            except (ValueError, TypeError):
                warnings.append(f"Valor inválido para '{field_name}': {ocr_value}")

        return None

    def _normalize_odd(
        self,
        ocr_odd,
        warnings: list[str],
    ) -> Optional[float]:
        """Normaliza odd total da imagem."""
        if ocr_odd is None:
            return None
        try:
            odd = float(str(ocr_odd).replace(",", "."))
            if odd < 1.0:
                warnings.append(f"Odd total {odd} parece inválida (< 1.0)")
            return round(odd, 4)
        except (ValueError, TypeError):
            warnings.append(f"Odd total inválida na imagem: {ocr_odd}")
            return None

    def _normalize_selections(
        self,
        ocr_selections: list,
        warnings: list[str],
    ) -> list[BetSelection]:
        """Normaliza as seleções extraídas da imagem."""
        selections = []

        for i, sel_data in enumerate(ocr_selections[:3], 1):  # Máx 3
            if not isinstance(sel_data, dict):
                continue

            odd_raw = sel_data.get("odd")
            odd = None
            if odd_raw is not None:
                try:
                    odd = float(str(odd_raw).replace(",", "."))
                except (ValueError, TypeError):
                    warnings.append(f"Seleção {i}: odd inválida '{odd_raw}' na imagem")

            selection = BetSelection(
                selection_order=i,
                description=str(sel_data.get("descricao", f"Seleção {i}"))[:500],
                odd=round(odd, 4) if odd is not None else None,
                event_name=sel_data.get("evento"),
                result_status="pending",
            )
            selections.append(selection)

        if not selections:
            warnings.append("Nenhuma seleção encontrada na imagem.")

        return selections
