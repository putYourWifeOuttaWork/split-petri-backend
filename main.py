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
