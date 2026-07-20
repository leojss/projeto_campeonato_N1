"""
agents/leitura_imagem.py — AgentLeituraImagem
Responsável por ler imagens de apostas via Google Gemini Vision usando o SDK moderno (google-genai).
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from typing import Optional

from google import genai
from PIL import Image
import io

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, MIN_OCR_CONFIDENCE


@dataclass
class ImageReadingResult:
    """Resultado da leitura da imagem pelo agente."""
    raw_text: str = ""
    ocr_json: dict = None
    confidence_score: float = 0.0
    error: Optional[str] = None
    needs_review: bool = False

    def __post_init__(self):
        if self.ocr_json is None:
            self.ocr_json = {}


# Prompt estruturado para extração de dados de apostas
# Foco enxuto: apenas o que o sistema realmente usa (odd total, a aposta
# descrita por extenso e a confiança da leitura). Valor apostado, retorno
# potencial e a quebra em seleções individuais não são necessários.
_EXTRACTION_PROMPT = textwrap.dedent("""
    Você é um especialista em leitura e análise de comprovantes de apostas esportivas.
    Analise a imagem fornecida e extraia as informações essenciais da aposta em formato estruturado.

    Retorne SOMENTE um JSON válido com a seguinte estrutura (sem markdown ```json, sem explicações):
    {
        "odd_total": número ou null,
        "aposta_descricao": "descrição completa em texto corrido com todas as seleções separadas por ponto e vírgula",
        "confianca": número de 0.0 a 1.0 indicando sua confiança na leitura,
        "selecoes": [
            {
                "event_name": "Nome do Jogo ou Evento (ex: Kalmar FF x Malmö FF)",
                "home_team": "Time Mandante ou null",
                "away_team": "Time Visitante ou null",
                "market": "gols | escanteios | cartoes | vencedor | ambos_marcam | outros",
                "type": "over | under | home_win | away_win | draw | yes | no | custom",
                "line": número da linha (ex: 1.5, 8.5) ou null,
                "odd": número da odd desta seleção ou null,
                "description": "Descrição clara do palpite desta seleção"
            }
        ]
    }

    Regras importantes:
    - "odd_total" deve usar ponto (.) como separador decimal.
    - "selecoes" deve conter a lista individualizada de cada palpite/jogo presente na imagem.
    - Se houver blocos agrupados tipo 'Criar Aposta' / 'Bet Builder', descreva as pernas do grupo ou crie uma seleção com o resumo dos palpites.
    - "confianca" deve refletir a qualidade da leitura (1.0 = perfeita, 0.0 = ilegível).
""").strip()


class AgentLeituraImagem:
    """
    Agente de leitura de imagens de apostas via Gemini Vision usando o SDK unificado (google-genai).
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY não configurada. "
                "Defina a variável no arquivo .env para habilitar a leitura de imagens."
            )
        # Inicializa o cliente do novo SDK google-genai
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def read_image(
        self,
        image_bytes: bytes,
        metadata: Optional[dict] = None,
    ) -> ImageReadingResult:
        """
        Processa uma imagem e extrai dados estruturados da aposta.

        Args:
            image_bytes: Conteúdo binário da imagem.
            metadata: Metadados opcionais da submissão (competitor_id, target_date, etc.)

        Returns:
            ImageReadingResult com texto bruto, JSON estruturado e score de confiança.
        """
        try:
            # Valida e abre a imagem
            image = self._load_image(image_bytes)

            from google.genai import types
            
            # Chama a geração de conteúdo do novo SDK
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[image, _EXTRACTION_PROMPT],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                )
            )

            raw_text = response.text.strip()
            ocr_json = self._parse_json(raw_text)
            confidence = float(ocr_json.get("confianca", 0.0))

            needs_review = confidence < MIN_OCR_CONFIDENCE

            return ImageReadingResult(
                raw_text=raw_text,
                ocr_json=ocr_json,
                confidence_score=confidence,
                needs_review=needs_review,
            )

        except Exception as e:
            return ImageReadingResult(
                raw_text="",
                ocr_json={},
                confidence_score=0.0,
                error=str(e),
                needs_review=True,
            )

    def _load_image(self, image_bytes: bytes):
        """Valida e converte bytes para objeto PIL Image."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()  # Verifica integridade
            return Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"Imagem inválida ou corrompida: {e}")

    def _parse_json(self, raw_text: str) -> dict:
        """
        Tenta extrair JSON da resposta do modelo.
        Trata casos onde o modelo adiciona markdown ao redor do JSON.
        """
        text = raw_text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {"confianca": 0.0, "erro_parse": True, "raw": text[:500]}
