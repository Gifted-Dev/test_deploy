import io
import PyPDF2
import docx
from ..utils.text import clean_text


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF."""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    return clean_text(" ".join(page.extract_text() or "" for page in pdf_reader.pages))


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extreact text from Docx."""
    doc = docx.Document(io.BytesIO(file_bytes))
    return clean_text(" ".join(p.text for p in doc.paragraph))


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from TXT."""
    return clean_text(file_bytes.decode("utf-8"))
