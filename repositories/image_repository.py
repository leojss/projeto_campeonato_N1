"""
repositories/image_repository.py — Acesso ao banco para imagens das apostas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from config.supabase_client import get_admin_client
from models.bet import BetImage


class ImageRepository:
    """Repositório para registros de imagens e OCR."""

    TABLE = "bet_images"

    @staticmethod
    def save_image_record(image: BetImage) -> BetImage:
        """Cria o registro inicial da imagem no banco (antes do OCR)."""
        client = get_admin_client()
        result = (
            client.table(ImageRepository.TABLE)
            .insert(image.to_dict())
            .execute()
        )
        data = result.data[0]
        image.id = data["id"]
        image.uploaded_at = data.get("uploaded_at")
        return image

    @staticmethod
    def update_ocr_result(
        image_id: str,
        ocr_text: str,
        ocr_json: dict,
        confidence_score: float,
        status: str,
    ) -> bool:
        """Persiste o resultado da leitura da IA."""
        client = get_admin_client()
        payload = {
            "ocr_text": ocr_text,
            "ocr_json": ocr_json,
            "confidence_score": confidence_score,
            "status": status,
            "processed_at": datetime.utcnow().isoformat(),
        }
        result = (
            client.table(ImageRepository.TABLE)
            .update(payload)
            .eq("id", image_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def get_image_by_bet(bet_id: str) -> Optional[BetImage]:
        """Retorna o registro de imagem associado a uma aposta."""
        client = get_admin_client()
        result = (
            client.table(ImageRepository.TABLE)
            .select("*")
            .eq("bet_id", bet_id)
            .order("uploaded_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        return BetImage(
            id=row.get("id"),
            bet_id=row.get("bet_id"),
            storage_path=row.get("storage_path", ""),
            original_filename=row.get("original_filename", ""),
            mime_type=row.get("mime_type", ""),
            file_size=row.get("file_size", 0),
            uploaded_at=row.get("uploaded_at"),
            processed_at=row.get("processed_at"),
            ocr_text=row.get("ocr_text"),
            ocr_json=row.get("ocr_json"),
            confidence_score=float(row["confidence_score"]) if row.get("confidence_score") is not None else None,
            status=row.get("status", "pending"),
        )

    @staticmethod
    def update_image_status(image_id: str, status: str) -> bool:
        """Atualiza apenas o status da imagem."""
        client = get_admin_client()
        result = (
            client.table(ImageRepository.TABLE)
            .update({"status": status})
            .eq("id", image_id)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def get_pending_images(limit: int = 20) -> list[BetImage]:
        """Retorna imagens aguardando processamento."""
        client = get_admin_client()
        result = (
            client.table(ImageRepository.TABLE)
            .select("*")
            .in_("status", ["pending", "failed"])
            .order("uploaded_at")
            .limit(limit)
            .execute()
        )
        images = []
        for row in result.data:
            images.append(BetImage(
                id=row.get("id"),
                bet_id=row.get("bet_id"),
                storage_path=row.get("storage_path", ""),
                original_filename=row.get("original_filename", ""),
                mime_type=row.get("mime_type", ""),
                file_size=row.get("file_size", 0),
                status=row.get("status", "pending"),
            ))
        return images
