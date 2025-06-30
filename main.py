from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jycxolmevsvrxmeinxff.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5Y3hvbG1ldnN2cnhtZWlueGZmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTEzMTQzNiwiZXhwIjoyMDY2NzA3NDM2fQ.RSZ2H5dccCwE1C58hq-DqKehHcnoaRBO0AhPQZ54gAI")
SUPABASE_STORAGE_BUCKET = "petri-images"

class SplitRequest(BaseModel):
    parent_image_url: str
    left_obs_id: str
    right_obs_id: str

@app.post("/split-petri-image")
async def split_petri_image(payload: SplitRequest):
    # Dummy: pretend we made two URLs (replace with real logic next)
    left_url = payload.parent_image_url + "?left"
    right_url = payload.parent_image_url + "?right"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    # PATCH left
    async with httpx.AsyncClient() as client:
        resp1 = await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.left_obs_id}",
            json={"image_url": left_url},
            headers=headers
        )
        resp2 = await client.patch(
            f"{SUPABASE_URL}/rest/v1/petri_observations?observation_id=eq.{payload.right_obs_id}",
            json={"image_url": right_url},
            headers=headers
        )
    return {
        "status": "ok",
        "received": payload.dict(),
        "left_resp": resp1.status_code,
        "right_resp": resp2.status_code,
    }
