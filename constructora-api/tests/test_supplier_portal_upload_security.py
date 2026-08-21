import unittest
from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, NameObject, TextStringObject

from app.api.v1.endpoints.supplier_portal import _validate_file


def _pdf_with_attachment(*, name: str, content: bytes, c2pa: bool) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_attachment(name, content)
    names = writer._root_object[NameObject("/Names")].get_object()
    embedded = names[NameObject("/EmbeddedFiles")].get_object()
    file_spec_reference = embedded[NameObject("/Names")][1]
    file_spec = file_spec_reference.get_object()
    if c2pa:
        file_spec[NameObject("/UF")] = TextStringObject(name)
        file_spec[NameObject("/Subtype")] = TextStringObject("application/c2pa")
        file_spec[NameObject("/AFRelationship")] = NameObject("/C2PA_Manifest")
        writer._root_object[NameObject("/AF")] = ArrayObject([file_spec_reference])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class SupplierPortalUploadSecurityTests(unittest.TestCase):
    def test_allows_verified_c2pa_content_credentials(self) -> None:
        content = _pdf_with_attachment(
            name="Content Credentials",
            content=b"\x00\x00\x00\x18jumb\x00\x00c2pa.assertions",
            c2pa=True,
        )

        extension, note = _validate_file("cotizacion.pdf", content)

        self.assertEqual(extension, ".pdf")
        self.assertIn("credenciales C2PA verificadas", note or "")

    def test_rejects_arbitrary_pdf_attachment(self) -> None:
        content = _pdf_with_attachment(
            name="datos.bin",
            content=b"contenido arbitrario",
            c2pa=False,
        )

        with self.assertRaisesRegex(HTTPException, "archivos adjuntos no permitidos"):
            _validate_file("cotizacion.pdf", content)


if __name__ == "__main__":
    unittest.main()
