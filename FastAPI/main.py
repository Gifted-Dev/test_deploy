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
import cloudinary.api
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

# Load environment variables from .env file
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Create temporary directory
os.makedirs("/tmp", exist_ok=True)

# Initialize the summarization pipeline with explicit cache directory
summarizer = pipeline(
    "summarization", 
    model="sshleifer/distilbart-cnn-12-6", 
    model_kwargs={"cache_dir": "/tmp/model_cache"}
)

ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
}

async def upload_to_cloudinary(file_path: str, resource_type: str = "raw") -> Optional[str]:
    """Upload a file to Cloudinary and return the URL."""
    try:
        result = cloudinary.uploader.upload(
            file_path,
            resource_type=resource_type,
            use_filename=True,
            unique_filename=True
        )
        return result['secure_url']
    except cloudinary.exceptions.Error as e:
        logger.error(f"Cloudinary upload failed: {str(e)}")
        return None

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

@app.post("/summarize/")
async def summarize_document(file: UploadFile = File(...)):
    """
    Endpoint to receive document file, extract text and generate summary.
    Supports PDF, DOCX, and TXT files.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}"
        )
    
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
    Returns a downloadable Word document URL from Cloudinary.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Create temporary directory for processing
    temp_dir = tempfile.mkdtemp(dir="/tmp")
    pdf_path = os.path.join(temp_dir, "input.pdf")
    docx_path = os.path.join(temp_dir, "output.docx")
    
    try:
        # Save uploaded PDF
        with open(pdf_path, "wb") as pdf_file:
            content = await file.read()
            pdf_file.write(content)
        
        # Convert PDF to DOCX
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()
        
        # Upload to Cloudinary
        docx_url = await upload_to_cloudinary(docx_path)
        
        if not docx_url:
            raise HTTPException(status_code=500, detail="Failed to upload converted document")
        
        return {"docx_url": docx_url}
        
    finally:
        # Clean up temporary files
        for file_path in [pdf_path, docx_path]:
            if os.path.exists(file_path):
                os.remove(file_path)
        os.rmdir(temp_dir)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy"}

port = int(os.environ.get("PORT", 8080))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)