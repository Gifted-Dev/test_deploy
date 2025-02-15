import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import document, health
from .services.cloudinary import init_cloudinary


# Initialize FastAPI App
app = FastAPI(title="Document Processing API")


# Configure CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize Cloudinary
init_cloudinary()

# Creatre temporary directory
os.makedirs("/tmp", exist_ok=True)

# Include routers
app.include_router(document.router, tags=["documents"])
app.include_router(health.router, tags=["health"])
