"""
agents/normalizacao_aposta.py — AgentNormalizacaoAposta
Converte a saída bruta da leitura da imagem em estrutura padronizada de aposta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from models.bet import BetSelection
from agents.leitura_imagem import ImageReadingResult


@dataclass
class NormalizedBet:
    """Aposta normalizada pronta para validação e persistência."""
    target_date: Optional[date] = None
    total_odd: Optional[float] = None
    aposta_descricao: Optional[str] = None
    selections: list[BetSelection] = None
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
            metadata: Dados informados no formulário (target_date).

        Returns:
            NormalizedBet com campos normalizados e warnings de inconsistência.
        """
        normalized = NormalizedBet(ocr_confidence=reading_result.confidence_score)
        ocr = reading_result.ocr_json or {}
        meta = metadata or {}

        # --- Data da aposta: sempre informada pelo formulário ---
        normalized.target_date = meta.get("target_date")

        # --- Odd total ---
        normalized.total_odd = self._normalize_odd(
            ocr.get("odd_total"),
            normalized.normalization_warnings,
        )

        # --- Descrição da aposta, escrita pela IA ---
        descricao = (
            ocr.get("aposta_descricao")
            or ocr.get("descricao")
            or ocr.get("description")
            or ocr.get("palpite")
        )
        if not descricao and reading_result.raw_text:
            cleaned = reading_result.raw_text.strip()
            if cleaned and not cleaned.startswith("{"):
                descricao = cleaned[:300]

        if descricao and str(descricao).strip() != "None":
            normalized.aposta_descricao = str(descricao).strip()
        else:
            normalized.aposta_descricao = "Comprovante enviado (Aguardando revisão manual)"
            normalized.normalization_warnings.append("OCR: Não foi possível identificar a descrição da aposta na imagem. Enviado para revisão manual.")

        # --- Seleções individuais ou agrupadas ---
        ocr_selecoes = ocr.get("selecoes")
        selections_list = []
        if isinstance(ocr_selecoes, list) and len(ocr_selecoes) > 0:
            for idx, sel_dict in enumerate(ocr_selecoes, 1):
                if isinstance(sel_dict, dict):
                    desc = sel_dict.get("description") or sel_dict.get("event_name") or "Seleção"
                    event = sel_dict.get("event_name")
                    odd_val = self._normalize_odd(sel_dict.get("odd"), [])
                    selections_list.append(BetSelection(
                        selection_order=idx,
                        description=str(desc).strip(),
                        event_name=str(event).strip() if event else None,
                        odd=odd_val or (normalized.total_odd if normalized.total_odd else 1.50),
                        result_status="pending",
                    ))

        if not selections_list:
            selections_list = [BetSelection(
                selection_order=1,
                description=normalized.aposta_descricao,
                odd=normalized.total_odd if normalized.total_odd else 1.50,
                result_status="pending",
            )]

        normalized.selections = selections_list
        return normalized

    def _normalize_odd(
        self,
        ocr_odd,
        warnings: list[str],
    ) -> Optional[float]:
        """Normaliza a odd total extraída da imagem."""
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
