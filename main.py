import os
import io
import re
import tempfile
import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
from pdf2docx import Converter
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import PyPDF2
import docx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Document Processing API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Create temporary directory
os.makedirs("/tmp", exist_ok=True)

# Initialize summarization pipeline
summarizer = pipeline(
    "summarization", 
    model="facebook/bart-large-cnn"
)

ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
}

def upload_to_cloudinary(file_path: str, resource_type: str = "raw") -> str:
    """Upload a file to Cloudinary and return the URL."""
    result = cloudinary.uploader.upload(
        file_path,
        resource_type=resource_type,
        use_filename=True,
        unique_filename=True
    )
    return result.get('secure_url', '')

def clean_text(text: str) -> str:
    """Clean extracted text."""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    return text

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF."""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    return clean_text(" ".join(page.extract_text() or "" for page in pdf_reader.pages))

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX."""
    doc = docx.Document(io.BytesIO(file_bytes))
    return clean_text(" ".join(p.text for p in doc.paragraphs))

def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from TXT."""
    return clean_text(file_bytes.decode('utf-8'))

def generate_summary(text: str) -> str:
    """Generate text summary."""
    max_chunk_length = 1024
    chunks = [text[i:i + max_chunk_length] for i in range(0, len(text), max_chunk_length)]
    return " ".join(
        summarizer(chunk, max_length=130, min_length=30, do_sample=False)[0]['summary_text']
        for chunk in chunks if len(chunk.split()) >= 50
    )

@app.post("/summarize/")
async def summarize_document(file: UploadFile = File(...)):
    """Extract and summarize text from a document."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    
    contents = await file.read()
    extractors = {
        'application/pdf': extract_text_from_pdf,
        'application/msword': extract_text_from_docx,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': extract_text_from_docx,
        'text/plain': extract_text_from_txt
    }
    extracted_text = extractors[file.content_type](contents)
    
    if not extracted_text:
        raise HTTPException(status_code=400, detail="No text extracted.")
    
    summary = generate_summary(extracted_text)
    if not summary:
        raise HTTPException(status_code=400, detail="Could not generate summary.")
    
    return {"filename": file.filename, "summary": summary}

@app.post("/convert-to-word/")
async def convert_pdf_to_word(file: UploadFile = File(...)):
    """Convert PDF to Word and return Cloudinary URL."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    temp_dir = tempfile.mkdtemp(dir="/tmp")
    pdf_path, docx_path = os.path.join(temp_dir, "input.pdf"), os.path.join(temp_dir, "output.docx")
    
    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(await file.read())
    
    cv = Converter(pdf_path)
    cv.convert(docx_path)
    cv.close()
    
    docx_url = upload_to_cloudinary(docx_path)
    if not docx_url:
        raise HTTPException(status_code=500, detail="Failed to upload converted document.")
    
    os.remove(pdf_path)
    os.remove(docx_path)
    os.rmdir(temp_dir)
    
    return {"docx_url": docx_url}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

port = int(os.getenv("PORT", 8080))
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=port)
