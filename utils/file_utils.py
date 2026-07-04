"""
utils/file_utils.py — Validação e manipulação de arquivos de imagem.
"""

from __future__ import annotations

import io
import os
import uuid
from typing import BinaryIO

from config.settings import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
)


class FileValidationError(Exception):
    """Erro de validação de arquivo de imagem."""
    pass


def validate_image_file(file_content: bytes, filename: str, mime_type: str | None = None) -> None:
    """
    Valida extensão, MIME type e tamanho de um arquivo de imagem.

    Args:
        file_content: Conteúdo binário do arquivo.
        filename: Nome original do arquivo.
        mime_type: MIME type declarado (opcional; será inferido se não fornecido).

    Raises:
        FileValidationError: Se alguma validação falhar.
    """
    # 1. Valida tamanho
    file_size = len(file_content)
    if file_size == 0:
        raise FileValidationError("O arquivo está vazio.")
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise FileValidationError(
            f"Arquivo muito grande: {actual_mb:.1f} MB. O tamanho máximo permitido é {max_mb:.0f} MB."
        )

    # 2. Valida extensão
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Extensão '{ext}' não permitida. Formatos aceitos: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 3. Valida magic bytes (primeiros bytes do arquivo)
    detected_mime = _detect_mime_from_bytes(file_content)
    if detected_mime and detected_mime not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"Tipo de arquivo detectado '{detected_mime}' não é uma imagem permitida. "
            f"Tipos aceitos: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # 4. Valida MIME type declarado (se fornecido)
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"Tipo MIME '{mime_type}' não permitido. Tipos aceitos: {', '.join(ALLOWED_MIME_TYPES)}"
        )


def _detect_mime_from_bytes(data: bytes) -> str | None:
    """
    Detecta o MIME type verificando os magic bytes do arquivo.
    Não requer dependências externas.
    """
    if data[:3] == b'\xff\xd8\xff':
        return "image/jpeg"
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    return None


def get_mime_from_extension(filename: str) -> str:
    """Retorna o MIME type com base na extensão do arquivo."""
    ext = os.path.splitext(filename.lower())[1]
    mapping = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return mapping.get(ext, "application/octet-stream")


def generate_storage_path(competitor_id: str, bet_id: str, filename: str) -> str:
    """
    Gera o caminho padronizado para armazenamento no Supabase Storage.

    Formato: {competitor_id}/{bet_id}/{uuid}_{filename}

    Args:
        competitor_id: UUID do competidor.
        bet_id: UUID da aposta.
        filename: Nome original do arquivo.

    Returns:
        Caminho relativo dentro do bucket.
    """
    _, ext = os.path.splitext(filename.lower())
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return f"{competitor_id}/{bet_id}/{unique_name}"


def read_streamlit_file(uploaded_file) -> tuple[bytes, str, str]:
    """
    Lê um arquivo enviado via st.file_uploader do Streamlit.

    Returns:
        Tupla (content_bytes, filename, mime_type)
    """
    content = uploaded_file.read()
    filename = uploaded_file.name
    mime_type = getattr(uploaded_file, "type", get_mime_from_extension(filename))
    return content, filename, mime_type
