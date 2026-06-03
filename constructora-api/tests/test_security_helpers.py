import unittest

from cryptography.fernet import Fernet


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


if __name__ == "__main__":
    unittest.main()
