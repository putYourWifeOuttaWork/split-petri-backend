# main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI()

class SplitRequest(BaseModel):
    parent_image_url: str
    left_obs_id: str
    right_obs_id: str

@app.post("/split-petri-image")
async def split_petri_image(payload: SplitRequest):
    # For now, just echo the request
    print(f"Got split request: {payload}")
    # ... implement download, split, upload logic here ...
    return {"status": "ok", "received": payload.dict()}
