from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from transformers import pipeline
# from moviepy import VideoFileClip
from pdf2docx import Converter
import PyPDF2
import docx
import io
import re
import os
import tempfile
# from typing import List
# import mimetypes
# import aiohttp

app = FastAPI(title="Document Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your frontend URL for better security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the summarization pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
}

def clean_text(text: str) -> str:
    """Clean extracted text by removing extra whitespace and newlines."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    text = re.sub(r'([.,!?])(\w)', r'\1 \2', text)
    return text.strip()

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += clean_text(page_text) + " "
    return clean_text(text)

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes."""
    doc = docx.Document(io.BytesIO(file_bytes))
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + " "
    return clean_text(text)

def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from TXT bytes."""
    text = file_bytes.decode('utf-8')
    return clean_text(text)

def generate_summary(text: str) -> str:
    """Generate summary using the BART model."""
    max_chunk_length = 1024
    chunks = [text[i:i + max_chunk_length] for i in range(0, len(text), max_chunk_length)]
    
    summaries = []
    for chunk in chunks:
        if len(chunk.split()) >= 50:
            summary = summarizer(chunk, max_length=130, min_length=30, do_sample=False)
            summaries.append(summary[0]['summary_text'])
    return " ".join(summaries)

def create_word_document(text: str, filename: str) -> str:
    """Create a Word document from text and return the file path."""
    doc = docx.Document()
    doc.add_paragraph(text)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    doc.save(temp_file.name)
    return temp_file.name


@app.post("/summarize/")
async def summarize_document(file: UploadFile = File(...)):
    """
    Endpoint to receive document file, extract text and generate summary.
    Supports PDF, DOCX, and TXT files.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, 
                          detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}")
    
    contents = await file.read()
    
    # Extract text based on file type
    if file.content_type == 'application/pdf':
        extracted_text = extract_text_from_pdf(contents)
    elif file.content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        extracted_text = extract_text_from_docx(contents)
    else:  # text/plain
        extracted_text = extract_text_from_txt(contents)
    
    if not extracted_text:
        raise HTTPException(status_code=400, detail="No text could be extracted from the document")
    
    summary = generate_summary(extracted_text)
    
    if not summary:
        raise HTTPException(status_code=400, detail="Could not generate summary from the extracted text")
    
    return {
        "filename": file.filename,
        "summary": summary
    }

@app.post("/convert-to-word/")
async def convert_pdf_to_word(file: UploadFile = File(...)):
    """
    Convert PDF document to Word format while preserving formatting.
    Returns a downloadable Word document.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Create temporary file for PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as pdf_temp:
        content = await file.read()
        pdf_temp.write(content)
        pdf_temp.flush()
        
        # Create output Word document path
        docx_path = os.path.splitext(pdf_temp.name)[0] + '.docx'
        
        # Convert PDF to DOCX
        cv = Converter(pdf_temp.name)
        cv.convert(docx_path)
        cv.close()
    
    # Remove the temporary PDF file after converter is closed
    os.unlink(pdf_temp.name)
    
    if not os.path.exists(docx_path):
        raise HTTPException(status_code=500, detail="Failed to create Word document")
    
    # Return the file
    response = FileResponse(
        docx_path,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename=os.path.splitext(file.filename)[0] + '.docx'
    )
    
    # Define cleanup function for DOCX file
    def cleanup_files():
        os.remove(docx_path)
    
    # Schedule cleanup after response is sent
    response.background = cleanup_files
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Default to 8000 if PORT is not set
    uvicorn.run(app, host="0.0.0.0", port=port)