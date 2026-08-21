import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.emailer import (
    purchase_order_email_content,
    supplier_invoice_correction_email_content,
)


class PurchaseOrderEmailTest(unittest.TestCase):
    def setUp(self) -> None:
        self.order = SimpleNamespace(
            po_number="OC-TEST-001",
            supplier=SimpleNamespace(name="Proveedor Prueba"),
            project=SimpleNamespace(name="Desarrollo Prueba"),
            issued_at=date(2026, 8, 21),
            expected_delivery_date=date(2026, 8, 28),
            payment_terms_days=30,
            subtotal=Decimal("12345.67"),
            notes="Entregar en bodega principal",
            items=[
                SimpleNamespace(
                    description="Material uno",
                    unit="PZA",
                    quantity_ordered=Decimal("10.00"),
                    unit_price=Decimal("1234.567"),
                    line_total=Decimal("12345.67"),
                )
            ],
        )

    def test_purchase_order_includes_secure_invoice_portal(self) -> None:
        portal_url = "https://acsm.example/supplier/invoice/token-123"

        subject, text_body, html_body = purchase_order_email_content(
            self.order,
            invoice_portal_url=portal_url,
        )

        self.assertIn("OC-TEST-001", subject)
        self.assertIn("10 PZA", text_body)
        self.assertIn(portal_url, text_body)
        self.assertIn("Enviar factura", html_body)
        self.assertIn(portal_url, html_body)

    def test_correction_email_includes_reason_and_fresh_link(self) -> None:
        portal_url = "https://acsm.example/supplier/invoice/fresh-token"
        reason = "El XML no corresponde al PDF <revisar>"

        subject, text_body, html_body = supplier_invoice_correction_email_content(
            self.order,
            portal_url=portal_url,
            reason=reason,
        )

        self.assertIn("OC-TEST-001", subject)
        self.assertIn(reason, text_body)
        self.assertIn(portal_url, text_body)
        self.assertIn("&lt;revisar&gt;", html_body)
        self.assertIn(portal_url, html_body)


if __name__ == "__main__":
    unittest.main()
