"""
tests/test_upload_service.py — Testes do UploadService e utilitários de arquivo.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from services.upload_service import UploadService, DeadlineError
from utils.file_utils import validate_image_file, generate_storage_path, FileValidationError

# Bytes mágicos para imagens de teste
JPEG_MAGIC = b'\xff\xd8\xff' + b'\x00' * 100
PNG_MAGIC = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
WEBP_MAGIC = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 100
INVALID_MAGIC = b'PK\x03\x04' + b'\x00' * 100  # ZIP file


class TestDeadlineValidation:
    """Testes de validação do prazo de upload."""

    @patch("services.upload_service.is_deadline_passed", return_value=False)
    def test_upload_before_deadline_passes(self, mock_deadline):
        """Upload dentro do prazo deve passar sem exceção."""
        UploadService.validate_upload(JPEG_MAGIC, "aposta.jpg", "image/jpeg", date.today() + timedelta(days=1))

    @patch("services.upload_service.is_deadline_passed", return_value=True)
    def test_upload_after_deadline_raises(self, mock_deadline):
        """Upload após prazo deve lançar DeadlineError."""
        with pytest.raises(DeadlineError, match="Prazo de envio expirado"):
            UploadService.validate_upload(JPEG_MAGIC, "aposta.jpg", "image/jpeg", date.today())


class TestFileValidation:
    """Testes de validação de arquivo de imagem."""

    def test_valid_jpeg(self):
        validate_image_file(JPEG_MAGIC, "foto.jpg", "image/jpeg")

    def test_valid_png(self):
        validate_image_file(PNG_MAGIC, "foto.png", "image/png")

    def test_valid_webp(self):
        validate_image_file(WEBP_MAGIC, "foto.webp", "image/webp")

    def test_empty_file_raises(self):
        with pytest.raises(FileValidationError, match="vazio"):
            validate_image_file(b"", "foto.jpg", "image/jpeg")

    def test_invalid_extension_raises(self):
        with pytest.raises(FileValidationError, match="Extensão"):
            validate_image_file(JPEG_MAGIC, "foto.gif", "image/gif")

    def test_pdf_extension_raises(self):
        with pytest.raises(FileValidationError, match="Extensão"):
            validate_image_file(JPEG_MAGIC, "aposta.pdf", "application/pdf")

    def test_file_too_large_raises(self):
        large_file = b'\xff\xd8\xff' + b'\x00' * (11 * 1024 * 1024)  # 11 MB
        with pytest.raises(FileValidationError, match="grande"):
            validate_image_file(large_file, "foto.jpg", "image/jpeg")

    def test_invalid_magic_bytes_raises(self):
        """Arquivo com extensão .jpg mas magic bytes de ZIP deve ser rejeitado."""
        with pytest.raises(FileValidationError, match="não é uma imagem"):
            validate_image_file(INVALID_MAGIC, "aposta.jpg", "image/jpeg")

    def test_exactly_max_size_passes(self):
        """Arquivo de exatamente 10MB deve passar."""
        ten_mb = b'\xff\xd8\xff' + b'\x00' * (10 * 1024 * 1024 - 3)
        validate_image_file(ten_mb, "foto.jpg", "image/jpeg")


class TestStoragePath:
    """Testes de geração de paths no Storage."""

    def test_path_format(self):
        path = generate_storage_path("comp-123", "bet-456", "foto.jpg")
        parts = path.split("/")
        assert parts[0] == "comp-123"
        assert parts[1] == "bet-456"
        assert parts[2].endswith(".jpg")

    def test_path_unique(self):
        path1 = generate_storage_path("comp-123", "bet-456", "foto.jpg")
        path2 = generate_storage_path("comp-123", "bet-456", "foto.jpg")
        assert path1 != path2  # UUID garante unicidade

    def test_extension_preserved(self):
        path = generate_storage_path("c1", "b1", "imagem.PNG")
        assert path.endswith(".png")
