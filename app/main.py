
import os
import secrets
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.meme_pipeline import generate_complete_meme


# =====================================================
# CONFIGURATION
# =====================================================

load_dotenv()

app = FastAPI(title="365 Days of Cramming API")

# app/temp/memes directory
APP_DIR = Path(__file__).resolve().parent
TEMP_IMAGE_DIR = APP_DIR / "temp" / "memes"

# Public Render URL (configured later in Render)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Secret used to protect the DELETE endpoint
DELETE_API_TOKEN = os.getenv("DELETE_API_TOKEN", "")


# =====================================================
# REQUEST MODEL
# =====================================================

class MemeRequest(BaseModel):
    target_audience: str = "College Students"
    platform: str = "Instagram"
    meme_format: str = "Single Image Meme"
    language: str = "Conversational English"
    max_attempts: int = 5
    cooldown_seconds: int = 5


# =====================================================
# IMAGE PATH VALIDATION
# =====================================================

def get_image_path(image_id: str) -> Path:

    # Prevent directory traversal
    if Path(image_id).name != image_id or image_id in {".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="Invalid image ID."
        )

    if not image_id.lower().endswith(".png"):
        raise HTTPException(
            status_code=400,
            detail="Invalid image format."
        )

    image_path = (TEMP_IMAGE_DIR / image_id).resolve()

    try:
        image_path.relative_to(TEMP_IMAGE_DIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid image location."
        )

    return image_path


# =====================================================
# 1. HEALTH CHECK
# =====================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy",
        "message": "365 Days of Cramming API is running"
    }


# =====================================================
# 2. GENERATE MEME
# =====================================================

@app.post(
    "/api/v1/generate-meme",
    response_model=dict
)
def generate_meme(request_data: MemeRequest, request: Request):

    try:

        # Execute existing AI pipeline
        result = generate_complete_meme(
            target_audience=request_data.target_audience,
            platform=request_data.platform,
            meme_format=request_data.meme_format,
            language=request_data.language,
            max_attempts=request_data.max_attempts,
            cooldown_seconds=request_data.cooldown_seconds
        )

        # Check pipeline result
        if result.get("status") != "success":
            raise HTTPException(
                status_code=500,
                detail=result.get("error") or
                f"Meme generation failed: {result.get('status')}"
            )

        # Get generated image path
        image_path_value = result.get("image_path")

        if not image_path_value:
            raise HTTPException(
                status_code=500,
                detail="Generated image path is missing."
            )

        image_path = Path(image_path_value).resolve()

        # Ensure image belongs to our temporary folder
        try:
            image_path.relative_to(TEMP_IMAGE_DIR.resolve())
        except ValueError:
            raise HTTPException(
                status_code=500,
                detail="Generated image is outside the temporary image folder."
            )

        # Check image exists
        if not image_path.is_file():
            raise HTTPException(
                status_code=500,
                detail="Generated image file was not found."
            )

        # Get complete Instagram caption
        instagram_caption = result.get("instagram_caption")

        if not instagram_caption:
            raise HTTPException(
                status_code=500,
                detail="Instagram caption is missing."
            )

        # Use image filename as unique image ID
        image_id = image_path.name

        # Create public image URL
        if PUBLIC_BASE_URL:

            image_url = (
                f"{PUBLIC_BASE_URL}/media/{quote(image_id)}"
            )

        else:

            image_url = str(
                request.url_for(
                    "get_meme_image",
                    image_id=image_id
                )
            )

        # Return ONLY the information n8n needs
        return {
            "image_url": image_url,
            "instagram_caption": instagram_caption
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Meme generation failed: {str(e)}"
        )


# =====================================================
# 3. SERVE GENERATED IMAGE
# =====================================================

@app.get(
    "/media/{image_id}",
    name="get_meme_image"
)
def get_meme_image(image_id: str):

    image_path = get_image_path(image_id)

    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Image not found or already deleted."
        )

    # Send actual image bytes to Instagram
    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=image_path.name
    )


# =====================================================
# 4. DELETE TEMPORARY IMAGE
# =====================================================

@app.delete("/api/v1/media/{image_id}")
def delete_meme_image(
    image_id: str,
    x_delete_token: str = Header(
        default="",
        alias="X-Delete-Token"
    )
):

    # Require a configured secret
    if not DELETE_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Image deletion is not configured."
        )

    # Verify deletion token
    if not secrets.compare_digest(
        x_delete_token,
        DELETE_API_TOKEN
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid deletion token."
        )

    image_path = get_image_path(image_id)

    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Image not found or already deleted."
        )

    try:

        image_path.unlink()

        return {
            "status": "deleted",
            "image_id": image_id
        }

    except OSError as e:

        raise HTTPException(
            status_code=500,
            detail=f"Could not delete image: {str(e)}"
        )
