import os
import tempfile
from pdf2docx import Converter
from .cloudinary import upload_to_cloudinary


def convert_pdf_to_docx(file_bytes: bytes) -> str:
    """Convert PDF to Docx and upload to Cloudinary."""
    temp_dir = tempfile.mkdtemp(dir="/tmp")
    pdf_path = os.path.join(temp_dir, "input.pdf")
    docx_path = os.path.join(temp_dir, "output.pdf")

    try:
        with open(pdf_path, "wb") as pdf_file:
            pdf_file.write(file_bytes)

        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()

        docx_url = upload_to_cloudinary(docx_path)
        return docx_url
    finally:
        # Cleanup
        for path in [pdf_path, docx_path]:
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
