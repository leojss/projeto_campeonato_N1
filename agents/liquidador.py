"""
agents/liquidador.py — AgentLiquidador
Utiliza o SDK moderno (google-genai) com pesquisa no Google (Search Grounding)
para conferir os resultados reais de jogos de futebol e liquidar as seleções.
"""

from __future__ import annotations

import json
import textwrap
from typing import Optional
from datetime import datetime

from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from models.bet import BetSelection


class AgentLiquidador:
    """
    Agente de IA resolutor de resultados de apostas via Gemini Search Grounding.
    Pesquisa dados do mundo real e julga se a tip venceu ou perdeu.
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY não configurada. "
                "Defina a variável no arquivo .env para habilitar o resolvedor automático."
            )
        # Inicializa o cliente do SDK google-genai
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def resolve_selection(self, selection: BetSelection) -> dict:
        """
        Consulta os resultados do jogo na web e julga o status da seleção.

        Args:
            selection: A seleção de aposta com descrição do palpite e evento.

        Returns:
            Dicionário com keys: 'result_status', 'justificativa', 'fontes' (lista de URLs).
        """
        # Formata a data do evento para facilitar a busca do modelo
        event_date_str = ""
        if selection.event_datetime:
            if isinstance(selection.event_datetime, str):
                try:
                    dt = datetime.fromisoformat(selection.event_datetime)
                    event_date_str = dt.strftime("%d/%m/%Y")
                except ValueError:
                    event_date_str = selection.event_datetime
            else:
                event_date_str = selection.event_datetime.strftime("%d/%m/%Y")

        prompt = textwrap.dedent(f"""
            Você é um auditor imparcial e especialista em resultados esportivos.
            Sua tarefa é verificar o resultado real de uma partida de futebol para liquidar uma aposta.
            
            Informações sobre o palpite/seleção:
            - Jogo / Evento: {selection.event_name or "Não especificado"}
            - Data estimada do evento: {event_date_str}
            - Palpite / Descrição da Tip: {selection.description}
            - Odd cadastrada: {selection.odd}

            Instruções:
            1. Use sua ferramenta de pesquisa (Google Search) para descobrir as estatísticas e o resultado real da partida (placar final, escanteios, gols, cartões, chutes a gol, resultado do 1º tempo, ou qualquer dado relevante que o palpite exija).
               - Priorize o site flashscore.com.br como fonte principal — ele traz placar, estatísticas completas (gols, escanteios, cartões, chutes) e o resultado por tempo (1º/2º tempo) de forma estruturada e confiável. Faça uma busca como "site:flashscore.com.br {selection.event_name or selection.description}" para localizar a página exata da partida, e abra a aba de estatísticas quando o mercado exigir dado além do placar (ex: escanteios, cartões, chutes a gol).
               - Se a partida não for encontrada no Flashscore (liga muito regional, jogo amistoso não coberto, etc.), use como alternativa sofascore.com, ge.globo.com/futebol, ou o site oficial da competição/liga.
            2. Analise friamente se o palpite (ex: "Mais de 1.5 gols", "Resultado final: Argentina", "Menos de 7.5 escanteios 1T") foi cumprido.
            3. Responda estritamente sob as regras das apostas esportivas tradicionais.
            
            Julgue o resultado da seleção em um dos seguintes status:
            - 'won' (se o palpite foi correto/cumprido)
            - 'lost' (se o palpite falhou/não foi cumprido)
            - 'void' (se o jogo foi cancelado, adiado por mais de 24 horas, ou se a regra do mercado anula a aposta, ex: Empate Anula Aposta onde o jogo terminou empatado)
            - 'pending' (apenas se o jogo ainda não aconteceu, está em andamento, ou se as informações disponíveis na web são totalmente insuficientes/inseguras para julgar)

            Retorne SOMENTE um JSON válido com a seguinte estrutura (sem markdown ```json, sem explicações):
            {{
                "result_status": "won|lost|void|pending",
                "justificativa": "Descrição clara dos fatos do jogo. Ex: O jogo terminou 3-1 para Argentina, totalizando 4 gols na partida. Logo, o palpite de 'Mais de 1.5 gols' foi vitorioso.",
                "fontes": ["lista de URLs dos sites de notícias/esportes consultados"]
            }}
        """).strip()

        import time
        max_retries = 3
        backoff_delay = 5.0

        for attempt in range(1, max_retries + 1):
            try:
                # Habilita o recurso oficial de Google Search Grounding no Gemini 3.5 Flash
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.0,  # Zero para máxima factualidade e consistência
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )

                raw_text = response.text.strip()
                result_json = self._parse_json(raw_text)

                # Tenta pegar as fontes de pesquisa reais fornecidas pela metadata de grounding da resposta
                sources = []
                try:
                    # O SDK google-genai traz as fontes de grounding em candidates[0].grounding_metadata
                    metadata = response.candidates[0].grounding_metadata
                    if metadata and metadata.grounding_chunks:
                        for chunk in metadata.grounding_chunks:
                            if chunk.web and chunk.web.uri:
                                sources.append(chunk.web.uri)
                except Exception:
                    pass

                # Mescla as fontes detectadas na metadata com as que a IA escreveu no JSON
                json_sources = result_json.get("fontes", [])
                if isinstance(json_sources, list):
                    sources.extend(json_sources)
                
                # Remove duplicados
                sources = list(set(sources))
                result_json["fontes"] = sources[:5]  # Limita a 5 fontes principais

                # Garante que o status retornado seja válido
                valid_statuses = ["won", "lost", "void", "pending"]
                status = result_json.get("result_status", "pending").lower()
                if status not in valid_statuses:
                    status = "pending"
                result_json["result_status"] = status

                return result_json

            except Exception as e:
                error_msg = str(e)
                # Se for erro de quota/rate limit (429 ou RESOURCE_EXHAUSTED) e houver tentativas restantes, aguarda
                if ("429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower()) and attempt < max_retries:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0  # Dobra o delay
                    continue
                else:
                    return {
                        "result_status": "pending",
                        "justificativa": f"Erro interno ao chamar resolvedor de IA: {e}",
                        "fontes": []
                    }

    def _parse_json(self, raw_text: str) -> dict:
        """Extrai JSON da resposta tratando eventuais markdowns."""
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
            return {
                "result_status": "pending",
                "justificativa": "Falha de parse no JSON retornado pela IA.",
                "fontes": []
            }
