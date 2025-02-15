import cloudinary
import cloudinary.uploader
from ..config import settings


def init_cloudinary():
    """Initialize Cloudinary configurations."""
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )


def upload_to_cloudinary(file_path: str, resource_type: str = "raw") -> str:
    """Upload a file to Cloudinary and return the URL."""
    result = cloudinary.uploader.upload(
        file_path, resource_type, use_filename=True, unique_filename=True
    )
    return result.get("secure_url", "")
