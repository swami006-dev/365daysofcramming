
import asyncio
import logging
import os
import secrets
import time

from contextlib import asynccontextmanager
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

# Enable application logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# app/temp/memes directory
APP_DIR = Path(__file__).resolve().parent
TEMP_IMAGE_DIR = APP_DIR / "temp" / "memes"

# Public Render URL
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Secret used to protect the manual DELETE endpoint


# Automatic cleanup settings
IMAGE_RETENTION_SECONDS = 3 * 60  # 3 minutes
CLEANUP_INTERVAL_SECONDS = 60     # Check every 1 minute


# =====================================================
# AUTOMATIC IMAGE CLEANUP
# =====================================================

def cleanup_expired_images() -> int:
    """
    Delete PNG images older than the configured retention period.

    Returns:
        Number of successfully deleted images.
    """

    TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    current_time = time.time()
    deleted_count = 0

    for image_path in TEMP_IMAGE_DIR.iterdir():

        try:

            # Process only PNG files
            if not image_path.is_file():
                continue

            if image_path.suffix.lower() != ".png":
                continue

            # Calculate image age
            modified_time = image_path.stat().st_mtime
            image_age = current_time - modified_time

            # Delete images older than 3 minutes
            if image_age >= IMAGE_RETENTION_SECONDS:

                image_path.unlink()
                deleted_count += 1

                logger.info(
                    "Deleted expired image: %s",
                    image_path.name
                )

        except FileNotFoundError:
            # Another process may have already deleted the file
            continue

        except OSError as error:

            logger.warning(
                "Could not delete image %s: %s",
                image_path.name,
                error
            )

    return deleted_count


async def automatic_cleanup_worker():
    """
    Automatically check the image folder every minute.
    """

    logger.info("Automatic image cleanup worker started.")

    while True:

        try:

            # Run filesystem operations without blocking
            # the FastAPI event loop
            deleted_count = await asyncio.to_thread(
                cleanup_expired_images
            )

            if deleted_count > 0:

                logger.info(
                    "Cleanup completed. Deleted %s image(s).",
                    deleted_count
                )

        except Exception:

            logger.exception(
                "An error occurred during automatic image cleanup."
            )

        # Wait before checking again
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


# =====================================================
# FASTAPI LIFESPAN
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Ensure the temporary image directory exists
    TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Start automatic cleanup when the server starts
    cleanup_task = asyncio.create_task(
        automatic_cleanup_worker()
    )

    logger.info("365 Days of Cramming API started.")

    try:

        yield

    finally:

        # Stop cleanup worker when server shuts down
        cleanup_task.cancel()

        try:
            await cleanup_task

        except asyncio.CancelledError:
            pass

        logger.info("Automatic image cleanup worker stopped.")


# =====================================================
# FASTAPI APPLICATION
# =====================================================

app = FastAPI(
    title="365 Days of Cramming API",
    lifespan=lifespan
)


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
def generate_meme(
    request_data: MemeRequest,
    request: Request
):

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

        # Return information required by Make.com
        return {
            "image_url": image_url,
            "instagram_caption": instagram_caption
        }

    except HTTPException:
        raise

    except Exception as error:

        logger.exception("Meme generation failed.")

        raise HTTPException(
            status_code=500,
            detail=f"Meme generation failed: {str(error)}"
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

    except OSError as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not delete image: {str(error)}"
        )
