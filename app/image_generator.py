
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

WORKER_URL = "https://image-api.lakshamanaswami006.workers.dev/"
CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY")

# Temporary image storage
APP_DIR = Path(__file__).resolve().parent
TEMP_IMAGE_DIR = APP_DIR / "temp" / "memes"


def generate_image_from_api(
    prompt_text,
    output_path="insta_4_5.png",
    width=832,
    height=1040
):
    if not CLOUDFLARE_API_KEY:
        raise ValueError("CLOUDFLARE_API_KEY is missing.")

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt_text,
        "width": width,
        "height": height
    }

    response = requests.post(
        WORKER_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        raise Exception(
            f"Worker API error ({response.status_code}): {response.text}"
        )

    # Ensure the temporary folder exists
    TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Save image inside app/temp/memes
    filename = Path(output_path).name
    save_path = TEMP_IMAGE_DIR / filename

    with open(save_path, "wb") as file:
        file.write(response.content)

    return str(save_path)
