from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
from PIL import Image
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
    # Storage public URL format:
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{filename}"

@app.post("/split-petri-image")
async def split_petri_image(payload: SplitRequest):
    # 1. Download parent image
    img_resp = requests.get(payload.parent_image_url)
    img = Image.open(io.BytesIO(img_resp.content))
    width, height = img.size
    mid = width // 2

    # 2. Crop left and right
    left_img = img.crop((0, 0, mid, height))
    right_img = img.crop((mid, 0, width, height))

    # 3. Upload images to Supabase Storage
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

    # 4. Update left/right/parent observations: set image_url and split_processed = true
    async with httpx.AsyncClient() as client:
        # Left child
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.left_obs_id}",
            json={"image_url": left_url, "split_processed": True},
            headers=headers
        )
        # Right child
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.right_obs_id}",
            json={"image_url": right_url, "split_processed": True},
            headers=headers
        )
        # Parent
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
    }
