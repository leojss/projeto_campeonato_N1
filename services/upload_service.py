"""
services/upload_service.py — Gerenciamento de upload de imagens para o Supabase Storage.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from config.supabase_client import get_admin_client
from config.settings import STORAGE_BUCKET
from utils.datetime_utils import is_deadline_passed, get_upload_deadline
from utils.file_utils import (
    validate_image_file,
    generate_storage_path,
    FileValidationError,
)


class DeadlineError(Exception):
    """Erro de prazo de upload expirado."""
    pass


class UploadService:
    """Serviço de upload de imagens para o Supabase Storage."""

    @staticmethod
    def validate_upload(
        file_content: bytes,
        filename: str,
        mime_type: str,
        target_date: date,
    ) -> None:
        """
        Valida prazo e arquivo antes do upload.

        Raises:
            DeadlineError: Se o prazo de upload expirou.
            FileValidationError: Se o arquivo for inválido.
        """
        # 1. Valida prazo (dupla verificação backend)
        if is_deadline_passed(target_date):
            deadline = get_upload_deadline(target_date)
            raise DeadlineError(
                f"Prazo de envio expirado. O prazo para apostas em {target_date.strftime('%d/%m/%Y')} "
                f"era até {deadline.strftime('%d/%m/%Y às %H:%M')}."
            )

        # 2. Valida arquivo
        validate_image_file(file_content, filename, mime_type)

    @staticmethod
    def upload_image(
        file_content: bytes,
        filename: str,
        mime_type: str,
        competitor_id: str,
        bet_id: str,
    ) -> str:
        """
        Faz upload da imagem para o Supabase Storage.

        Args:
            file_content: Bytes da imagem.
            filename: Nome original do arquivo.
            mime_type: MIME type do arquivo.
            competitor_id: UUID do competidor.
            bet_id: UUID da aposta.

        Returns:
            storage_path: Caminho do arquivo no bucket.

        Raises:
            Exception: Se o upload falhar.
        """
        storage_path = generate_storage_path(competitor_id, bet_id, filename)
        client = get_admin_client()

        # Garante de forma automatizada que o bucket de imagens exista no Supabase Storage
        try:
            client.storage.create_bucket(STORAGE_BUCKET, {"public": False, "file_size_limit": 10485760})
        except Exception:
            # Ignora se o bucket já existir
            pass

        client.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type, "upsert": "false"},
        )

        return storage_path

    @staticmethod
    def get_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Gera uma URL assinada temporária para visualização da imagem.

        Args:
            storage_path: Caminho no bucket.
            expires_in: Tempo de expiração em segundos (padrão: 1 hora).

        Returns:
            URL assinada ou None em caso de erro.
        """
        try:
            client = get_admin_client()
            response = client.storage.from_(STORAGE_BUCKET).create_signed_url(
                storage_path, expires_in
            )
            return response.get("signedURL")
        except Exception as e:
            print(f"[UploadService] Erro ao gerar URL assinada: {e}")
            return None

    @staticmethod
    def delete_image(storage_path: str) -> bool:
        """Remove uma imagem do Storage (uso administrativo)."""
        try:
            client = get_admin_client()
            client.storage.from_(STORAGE_BUCKET).remove([storage_path])
            return True
        except Exception:
            return False
