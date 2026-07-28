import unittest
from decimal import Decimal

from app.services.invoice_analysis import parse_invoice_pdf_text, reconcile_invoice_items
from app.services.invoice_documents import (
    InvoiceDocumentError,
    parse_cfdi_xml,
    validate_invoice_file,
)


VALID_CFDI = b"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"
    Serie="A" Folio="104" Fecha="2026-07-20T10:30:00" SubTotal="1000.00"
    Moneda="MXN" Total="1160.00" MetodoPago="PUE" FormaPago="03">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor SA" />
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="Constructora SA" />
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="40142100" NoIdentificacion="MAT-001"
        Cantidad="5.0000" ClaveUnidad="H87" Unidad="PZA"
        Descripcion="TUBO PVC SANITARIO 51 MM" ValorUnitario="200.00"
        Importe="1000.00" />
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="160.00" />
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        UUID="2f8f838c-25bb-4a4b-b0a3-9e9023f58b21" />
  </cfdi:Complemento>
</cfdi:Comprobante>
"""


class InvoiceDocumentHelpersTest(unittest.TestCase):
    def test_parse_cfdi_extracts_fiscal_identity_and_amounts(self) -> None:
        parsed = parse_cfdi_xml(VALID_CFDI)

        self.assertEqual(parsed["fiscal_uuid"], "2F8F838C-25BB-4A4B-B0A3-9E9023F58B21")
        self.assertEqual(parsed["issuer_tax_id"], "AAA010101AAA")
        self.assertEqual(parsed["receiver_tax_id"], "BBB010101BBB")
        self.assertEqual(parsed["subtotal"], "1000.00")
        self.assertEqual(parsed["transferred_taxes"], "160.00")
        self.assertEqual(parsed["total"], "1160.00")
        concepts = parsed["concepts"]
        self.assertEqual(len(concepts), 1)
        self.assertEqual(concepts[0]["description"], "TUBO PVC SANITARIO 51 MM")
        self.assertEqual(concepts[0]["quantity"], "5.0000")

    def test_validate_xml_rejects_untimbrada_invoice(self) -> None:
        untimbrada = VALID_CFDI.replace(
            b'<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"\n        UUID="2f8f838c-25bb-4a4b-b0a3-9e9023f58b21" />',
            b"",
        )

        with self.assertRaisesRegex(InvoiceDocumentError, "UUID fiscal"):
            validate_invoice_file(
                file_name="factura.xml",
                content_type="application/xml",
                content=untimbrada,
                expected_type="xml",
            )

    def test_validate_pdf_rejects_active_content(self) -> None:
        with self.assertRaisesRegex(InvoiceDocumentError, "elementos activos"):
            validate_invoice_file(
                file_name="factura.pdf",
                content_type="application/pdf",
                content=b"%PDF-1.7\n1 0 obj << /JavaScript 2 0 R >> endobj",
                expected_type="pdf",
            )

    def test_validate_pdf_accepts_basic_document_and_hashes_it(self) -> None:
        content = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF"

        validated = validate_invoice_file(
            file_name="Factura 104.pdf",
            content_type="application/pdf",
            content=content,
            expected_type="pdf",
        )

        self.assertEqual(validated.document_type, "pdf")
        self.assertEqual(validated.original_file_name, "Factura 104.pdf")
        self.assertEqual(len(validated.sha256), 64)

    def test_pdf_text_extracts_header_and_material_rows(self) -> None:
        text = """
        FACTURA DEMO
        Folio: FACT-DEMO-002
        Fecha: 30/07/2026
        Moneda: MXN

        Material                          Unidad Cantidad Precio unitario Importe
        TUBO PVC SANITARIO 51 MM (2")     ML     339.75   $62.00          $21,064.50
        TUBO PVC SANITARIO 100 MM (4")    ML     195.75   $118.00         $23,098.50

        Subtotal $44,163.00
        IVA 16% $7,066.08
        TOTAL $51,229.08
        """

        parsed, rows = parse_invoice_pdf_text(text)

        self.assertEqual(parsed["folio"], "FACT-DEMO-002")
        self.assertEqual(parsed["issue_datetime"], "2026-07-30")
        self.assertEqual(parsed["total"], "51229.08")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].quantity, Decimal("339.75"))
        self.assertEqual(rows[0].unit_price, Decimal("62.00"))

    def test_reconciliation_matches_exact_material_and_limits_to_received(self) -> None:
        class Item:
            id = 10
            description = 'TUBO PVC SANITARIO 51 MM (2")'
            unit = "ML"
            received_quantity = Decimal("300")

        _, rows = parse_invoice_pdf_text(
            'TUBO PVC SANITARIO 51 MM (2")     ML     339.75   $62.00   $21,064.50'
        )
        analyses, warnings = reconcile_invoice_items(rows, [Item()], {})

        self.assertEqual(analyses[0]["purchase_order_item_id"], 10)
        self.assertEqual(analyses[0]["billable_quantity"], Decimal("300"))
        self.assertEqual(analyses[0]["match_status"], "limited")
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
