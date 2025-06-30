from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
from PIL import Image, ExifTags
import io
import requests

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jycxolmevsvrxmeinxff.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "YOUR_SERVICE_ROLE_KEY")
SUPABASE_STORAGE_BUCKET = "petri-images"

class SplitRequest(BaseModel):
    parent_obs_id: str
    parent_image_url: str
    left_obs_id: str
    right_obs_id: str

def auto_orient_pil_image(img):
    """Apply EXIF orientation so all mobile photos display as intended."""
    try:
        exif = img._getexif()
        if exif is not None:
            orientation_key = next(
                k for k, v in ExifTags.TAGS.items() if v == 'Orientation'
            )
            orientation = exif.get(orientation_key)
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except Exception:
        pass  # No EXIF or orientation info, just skip
    return img

def split_and_return_images(image_url):
    img_resp = requests.get(image_url)
    img = Image.open(io.BytesIO(img_resp.content))
    img = auto_orient_pil_image(img)
    width, height = img.size

    # Use a threshold to avoid rotating nearly square images
    if height / width > 1.1:
        # Portrait (tall): rotate 90°, then split vertically
        img = img.rotate(90, expand=True)
        width, height = img.size
        split_used = "portrait-rotated"
    else:
        # Landscape or nearly square: split vertically as-is
        split_used = "landscape-or-square"

    mid = width // 2
    left_img = img.crop((0, 0, mid, height))
    right_img = img.crop((mid, 0, width, height))
    return left_img, right_img, split_used

def upload_to_supabase_storage(file_bytes, filename, content_type="image/jpeg"):
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{filename}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": content_type,
    }
    resp = requests.post(url, headers=headers, data=file_bytes)
    if resp.status_code not in (200, 201):
        raise Exception(f"Storage upload failed: {resp.status_code} {resp.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{filename}"

@app.post("/split-petri-image")
async def split_petri_image(payload: SplitRequest):
    # 1. Download, EXIF-normalize, and auto-orient/split image
    left_img, right_img, split_used = split_and_return_images(payload.parent_image_url)

    # 2. Upload images to Supabase Storage
    left_buf = io.BytesIO()
    right_buf = io.BytesIO()
    left_img.save(left_buf, format="JPEG")
    right_img.save(right_buf, format="JPEG")
    left_buf.seek(0)
    right_buf.seek(0)
    left_filename = f"{payload.left_obs_id}.jpg"
    right_filename = f"{payload.right_obs_id}.jpg"
    left_url = upload_to_supabase_storage(left_buf.read(), left_filename)
    right_url = upload_to_supabase_storage(right_buf.read(), right_filename)

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    async with httpx.AsyncClient() as client:
        # 3. Archive the original image (for audit/AI/future)
        archive_payload = {
            "original_image_url": payload.parent_image_url,
            "main_petri_observation_id": payload.parent_obs_id,
            "split_method": split_used  # For future troubleshooting
        }
        archive_resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/split_petri_images",
            json=archive_payload,
            headers=headers
        )
        print("Archive insert response:", archive_resp.status_code, archive_resp.text)

        # 4. Update left/right/parent observations: set image_url and split_processed = true
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.left_obs_id}",
            json={"image_url": left_url, "split_processed": True},
            headers=headers
        )
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.right_obs_id}",
            json={"image_url": right_url, "split_processed": True},
            headers=headers
        )
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.parent_obs_id}",
            json={"split_processed": True},
            headers=headers
        )

    return {
        "status": "ok",
        "received": payload.dict(),
        "left_url": left_url,
        "right_url": right_url,
        "all_split_processed": True,
        "archived": True,
        "split_method": split_used
    }
