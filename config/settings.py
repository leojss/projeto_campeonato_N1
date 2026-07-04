"""
config/settings.py — Constantes globais e variáveis de ambiente.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Informações da aplicação
# ============================================================
APP_NAME = "Apostas N1"
APP_VERSION = "1.0.0"

# ============================================================
# Supabase
# ============================================================
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise EnvironmentError(
        "As variáveis SUPABASE_URL e SUPABASE_ANON_KEY são obrigatórias. "
        "Copie o arquivo .env.example para .env e preencha os valores."
    )

# ============================================================
# IA — Google Gemini Vision
# ============================================================
AI_PROVIDER: str = os.environ.get("AI_PROVIDER", "gemini")
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# Confiança mínima da IA para aprovar aposta automaticamente (0.0–1.0)
MIN_OCR_CONFIDENCE: float = float(os.environ.get("MIN_OCR_CONFIDENCE", "0.75"))

# ============================================================
# Regras de negócio
# ============================================================
# Fuso horário oficial do sistema
TIMEZONE: str = os.environ.get("TIMEZONE", "America/Sao_Paulo")

# Máximo de apostas por competidor por dia
MAX_BETS_PER_DAY: int = 2

# Odd mínima permitida por seleção e para a aposta total
MIN_ODD: float = 1.50

# Número máximo de seleções (combinadas) por aposta
MAX_COMBINED: int = 3

# Prazo de upload: horas e minutos do dia ANTERIOR ao target_date
UPLOAD_DEADLINE_HOUR: int = 23
UPLOAD_DEADLINE_MINUTE: int = 59

# ============================================================
# Upload de imagens
# ============================================================
# Nome do bucket no Supabase Storage
STORAGE_BUCKET: str = "bet-images"

# Tipos MIME permitidos para upload
ALLOWED_MIME_TYPES: list[str] = [
    "image/jpeg",
    "image/png",
    "image/webp",
]

# Extensões permitidas
ALLOWED_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png", ".webp"]

# Tamanho máximo do arquivo em bytes (10 MB)
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

# ============================================================
# Competição
# ============================================================
# ID fixo da competição ativa (definido no seed.sql)
ACTIVE_COMPETITION_ID: str = "c0000000-0000-0000-0000-000000000001"
