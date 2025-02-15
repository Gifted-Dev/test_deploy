from fastapi import APIRouter, UploadFile, File, HTTPException
from ..config import settings
from ..services.summarizer import summarizer
from ..services.extractor import (
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
)
from ..services.converter import convert_pdf_to_docx

router = APIRouter()


@router.post("/summarize")
async def summarize_document(file: UploadFile = File(...)):
    """Extract and summarize text from a document."""
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    contents = await file.read()
    extractors = {
        "application/pdf": extract_text_from_pdf,
        "text/plain": extract_text_from_txt,
        "application/msword": extract_text_from_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_text_from_docx,
    }

    extracted_text = extractors[file.content_type](contents)
    if not extracted_text:
        raise HTTPException(status_code=400, detail="No text extracted")

    summary = summarizer.generate_summary(extracted_text)
    if not summary:
        raise HTTPException(status_code=400, detail="Could not generate summary")

    return {"filename": file.filename, "summary": summary}


@router.post("/convert-to-word")
async def convert_pdf_to_word(file: UploadFile = File(...)):
    """Convert PDF to Word and return the Cloudinary URL."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    contents = await file.read()
    docx_url = convert_pdf_to_docx(contents)

    if not docx_url:
        raise HTTPException(
            status_code=400, detail="Failed to upload converted document."
        )

    return {"docx_url": docx_url}
