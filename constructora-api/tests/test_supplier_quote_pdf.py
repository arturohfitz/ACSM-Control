import unittest
from decimal import Decimal
from types import SimpleNamespace

from app.services.supplier_quote_pdf import (
    SupplierQuotePDFMismatchError,
    parse_supplier_quote_text,
)


QUOTE_TEXT = """
TUBERIAS Y CONEXIONES DEMO COTIZACION
Folio: COT-DEMO-004
DEL BAJIO, S.A. DE C.V. Fecha: 28/07/2026
Moneda: MXN
Proveedor ficticio para pruebas de sistema
Tel. (442) 000 2002 | cotizaciones.demo2@example.com

Solicitud de cotizacion: SC-202607-0002 Fecha requerida: 30/07/2026
Validez: 7 dias naturales

TUBO DE COBRE DE 19 mm TIPO M ML 122.25 $185.00 $22,616.25
TUBO DE COBRE DE 25 MM TRAM 11.6805 $920.00 $10,746.06
TUBO NEGRO DURMAN GAS DIAM. 16-20 ML 95.25 $98.00 $9,334.50
TUBO NEGRO DURMAN GAS DIAM. 12-16 ML 43.5 $74.00 $3,219.00
TUBO PVC SANITARIO DE 75MM TRAM 13.0002 $310.00 $4,030.06
TUBO PVC SANITARIO DE 150 MM TRAM 9.1248 $785.00 $7,162.97
TUBO PVC SANITARIO 38 MM (1 1/2") ML 202.5 $48.00 $9,720.00
TUBO PVC SANITARIO 51 MM (2") ML 339.75 $62.00 $21,064.50
TUBO PVC SANITARIO 100 MM (4") ML 195.75 $118.00 $23,098.50
TUBO CPVC HIDRAULICO DE 13 MM ML 449.25 $39.00 $17,520.75
TUBO DE CPVC SDR-11 DE 25 MM PZA 11.0655 $285.00 $3,153.67
TUBO CPVC CTS 19 MM ML 298.5 $52.00 $15,522.00

Subtotal $147,188.26
IVA 16% $23,550.12
TOTAL $170,738.38

- Entrega estimada: 2 a 4 dias habiles posteriores a la confirmacion.
- Forma de pago: Transferencia bancaria; 50% anticipo y 50% contra entrega.
"""


ITEMS = (
    ("TUBO DE COBRE DE 19 mm TIPO M", "ML", "122.2500"),
    ("TUBO DE COBRE DE 25 MM", "TRAM", "11.6805"),
    ("TUBO NEGRO DURMAN GAS DIAM. 16-20", "ML", "95.2500"),
    ("TUBO NEGRO DURMAN GAS DIAM. 12-16", "ML", "43.5000"),
    ("TUBO PVC SANITARIO DE 75MM", "TRAM", "13.0002"),
    ("TUBO PVC SANITARIO DE 150 MM", "TRAM", "9.1248"),
    ('TUBO PVC SANITARIO 38 MM (1 1/2")', "ML", "202.5000"),
    ('TUBO PVC SANITARIO 51 MM (2")', "ML", "339.7500"),
    ('TUBO PVC SANITARIO 100 MM (4")', "ML", "195.7500"),
    ("TUBO CPVC HIDRAULICO DE 13 MM", "ML", "449.2500"),
    ("TUBO DE CPVC SDR-11 DE 25 MM", "PZA", "11.0655"),
    ("TUBO CPVC CTS 19 MM", "ML", "298.5000"),
)


def _link(*, supplier_name: str = "Ferreteria Leon", rfq_number: str = "SC-202607-0002"):
    return SimpleNamespace(
        supplier=SimpleNamespace(
            name=supplier_name,
            legal_name=supplier_name,
            tax_id=None,
            contact_email="arturoh.fitz@gmail.com",
            payment_terms_days=30,
        ),
        rfq=SimpleNamespace(
            rfq_number=rfq_number,
            items=[
                SimpleNamespace(
                    id=index,
                    description=description,
                    unit=unit,
                    quantity=Decimal(quantity),
                )
                for index, (description, unit, quantity) in enumerate(ITEMS, start=1)
            ],
        ),
    )


class SupplierQuotePDFTest(unittest.TestCase):
    def test_extracts_all_prices_totals_and_flags_supplier_mismatch(self) -> None:
        analysis = parse_supplier_quote_text(QUOTE_TEXT, _link())

        self.assertEqual(analysis.payload.quote_number, "COT-DEMO-004")
        self.assertEqual(len(analysis.payload.items), 12)
        self.assertEqual(analysis.payload.items[0].unit_price, Decimal("185.00"))
        self.assertEqual(analysis.payload.items[-1].unit_price, Decimal("52.00"))
        self.assertEqual(analysis.payload.delivery_days, 4)
        self.assertEqual(analysis.document_subtotal, Decimal("147188.26"))
        self.assertEqual(analysis.document_tax_amount, Decimal("23550.12"))
        self.assertEqual(analysis.document_total, Decimal("170738.38"))
        self.assertEqual(analysis.supplier_match_status, "mismatch")
        self.assertIn("no coincide", analysis.validation_errors[0])
        self.assertGreaterEqual(analysis.confidence, Decimal("0.95"))

    def test_supplier_name_can_be_verified_from_document(self) -> None:
        analysis = parse_supplier_quote_text(
            QUOTE_TEXT,
            _link(supplier_name="Tuberias y Conexiones Demo del Bajio, S.A. de C.V."),
        )

        self.assertEqual(analysis.supplier_match_status, "matched")
        self.assertGreaterEqual(analysis.supplier_match_confidence, Decimal("0.90"))

    def test_rejects_document_for_another_rfq(self) -> None:
        with self.assertRaisesRegex(SupplierQuotePDFMismatchError, "no a SC-202607-9999"):
            parse_supplier_quote_text(QUOTE_TEXT, _link(rfq_number="SC-202607-9999"))


if __name__ == "__main__":
    unittest.main()
