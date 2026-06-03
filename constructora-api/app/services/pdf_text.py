import logging
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


logger = logging.getLogger(__name__)


class PDFTextExtractionError(RuntimeError):
    pass


class PDFTextEmptyError(PDFTextExtractionError):
    pass


def extract_pdf_text(file_bytes: bytes, file_name: str, *, timeout_seconds: int = 10) -> str:
    with tempfile.NamedTemporaryFile(suffix=Path(file_name).suffix or ".pdf") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", tmp.name, "-"],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            if completed.stdout.strip():
                return completed.stdout
        except FileNotFoundError:
            logger.info("pdftotext no esta disponible para extraer %s", file_name)
        except subprocess.SubprocessError as exc:
            logger.warning("pdftotext fallo al extraer %s: %s", file_name, exc)

    try:
        reader = PdfReader(BytesIO(file_bytes))
        text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
    except Exception as exc:
        logger.exception("No fue posible extraer texto del PDF %s", file_name)
        raise PDFTextExtractionError("No fue posible extraer texto del PDF") from exc

    if not text.strip():
        logger.warning("El PDF %s no contiene texto extraible", file_name)
        raise PDFTextEmptyError("El PDF no contiene texto extraible")
    return text
