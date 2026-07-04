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
_EXTRACTION_PROMPT = textwrap.dedent("""
    Você é um especialista em leitura de comprovantes de apostas esportivas.
    Analise a imagem fornecida e extraia todas as informações disponíveis sobre a aposta.

    Retorne SOMENTE um JSON válido com a seguinte estrutura (sem markdown, sem explicações):
    {
        "data_aposta": "YYYY-MM-DD ou null",
        "valor_apostado": número ou null,
        "selecoes": [
            {
                "descricao": "descrição do evento/seleção",
                "odd": número,
                "evento": "nome do evento ou null",
                "resultado": "pendente|ganhou|perdeu|anulada ou null"
            }
        ],
        "odd_total": número ou null,
        "retorno_potencial": número ou null,
        "bookmaker": "nome da casa de apostas ou null",
        "observacoes": "outras informações relevantes ou null",
        "confianca": número de 0.0 a 1.0 indicando sua confiança na leitura
    }

    Regras importantes:
    - odds devem usar ponto (.) como separador decimal
    - Se não conseguir ler algum campo com clareza, use null
    - "confianca" deve refletir a qualidade geral da leitura (1.0 = perfeita, 0.0 = ilegível)
    - Se a imagem não for um comprovante de aposta, use confianca = 0.0
    - **Identificação meticulosa de Múltiplas Seleções (Apostas Combinadas/Múltiplas)**:
      Se o comprovante contiver mais de um evento esportivo (ex: Dupla, Tripla ou Múltipla com jogos diferentes e linhas de odds separadas), você DEVE extrair e listar cada jogo/evento individualmente como um item separado na lista "selecoes". Leia e liste todas as seleções presentes com extrema precisão, garantindo que o número de itens em "selecoes" corresponda exatamente à quantidade de palpites independentes no comprovante.
    - **Tratamento de blocos de 'Criar Aposta' / 'Bet Builder' (comum na Betano e Bet365)**:
      Se o comprovante tiver um bloco agrupado do tipo 'Criar Aposta', esse bloco inteiro representa uma única seleção na aposta principal. A odd dessa seleção é a odd geral desse bloco (ex: a odd de 2.07 do grupo, e não as sub-odds ou sub-itens internos). A descrição da seleção deve ser o resumo dos palpites do grupo (ex: 'Criar Aposta: Argentina v Cabo Verde (Mais de 1.5 Gols, Menos de 7.5 Escanteios...)'). NÃO divida os sub-palpites do bloco em seleções separadas no JSON. Trate o grupo inteiro como uma única tip da aposta múltipla.
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
