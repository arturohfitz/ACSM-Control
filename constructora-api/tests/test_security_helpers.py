import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, item) -> None:
        self.added.append(item)


class SecurityHelpersTest(unittest.TestCase):
    def test_secret_encryption_roundtrip(self) -> None:
        from app.core.config import settings
        from app.services import secrets

        original_key = settings.email_encryption_key
        try:
            settings.email_encryption_key = Fernet.generate_key().decode("utf-8")
            encrypted = secrets.encrypt_secret("Acon456#")

            self.assertNotEqual(encrypted, "Acon456#")
            self.assertEqual(secrets.decrypt_secret(encrypted), "Acon456#")
        finally:
            settings.email_encryption_key = original_key

    def test_rfq_exception_fingerprint_is_stable(self) -> None:
        from app.api.v1.endpoints.purchasing import (
            _rfq_exception_fingerprint,
            _rfq_exception_snapshot,
        )
        from app.schemas.purchasing import SupplierRFQExceptionCreate

        payload = SupplierRFQExceptionCreate(
            project_id=1,
            title="Cemento",
            required_by=None,
            response_deadline=None,
            supplier_ids=[3, 1],
            request_notes="Solo hay dos proveedores disponibles",
            items=[
                {
                    "material_id": None,
                    "source_code": "MAT-1",
                    "description": " Cemento gris 50kg ",
                    "unit": " saco ",
                    "quantity": "100",
                    "notes": None,
                }
            ],
        )
        snapshot = _rfq_exception_snapshot(payload)

        self.assertEqual(snapshot["supplier_ids"], [1, 3])
        self.assertEqual(snapshot["items"][0]["description"], "Cemento gris 50kg")
        self.assertEqual(
            _rfq_exception_fingerprint(snapshot),
            _rfq_exception_fingerprint(dict(reversed(list(snapshot.items())))),
        )

    def test_queue_email_defaults_to_pending(self) -> None:
        from app.services.email_outbox import queue_email

        db = FakeSession()
        message = queue_email(
            db,
            company_id=1,
            requested_by=7,
            message_type="supplier_rfq",
            related_entity_type="SupplierRFQSupplier",
            related_entity_id=22,
            recipient_email=" proveedor@example.com ",
            subject="Solicitud",
            text_body="Contenido",
        )

        self.assertEqual(db.added, [message])
        self.assertEqual(message.status, "pending")
        self.assertEqual(message.recipient_email, "proveedor@example.com")
        self.assertEqual(message.related_entity_id, "22")
        self.assertEqual(message.attempts, 0)
        self.assertIsNotNone(message.next_attempt_at)

    def test_pdf_text_rejects_invalid_pdf(self) -> None:
        from app.services import pdf_text

        with (
            patch.object(pdf_text.subprocess, "run", side_effect=FileNotFoundError),
            patch.object(pdf_text, "PdfReader", side_effect=ValueError("archivo invalido")),
            patch.object(pdf_text.logger, "exception"),
            self.assertRaises(pdf_text.PDFTextExtractionError),
        ):
            pdf_text.extract_pdf_text(b"no es un pdf", "invalido.pdf", timeout_seconds=1)



if __name__ == "__main__":
    unittest.main()
