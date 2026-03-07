from __future__ import annotations

import uuid
from typing import Optional

import aiosqlite
from fastapi import APIRouter, File, UploadFile

from ..database import DB_PATH
from ..models import UploadResponse
from ..utils import now_iso


router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    job_id = str(uuid.uuid4())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO jobs (id, name, created_at, status, current_step, progress, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, file.filename or "upload.txt", now_iso(), "uploaded", "Uploaded", 0.0, None),
        )
        await db.execute(
            "INSERT OR REPLACE INTO documents (job_id, filename, content) VALUES (?, ?, ?)",
            (job_id, file.filename or "upload.txt", text),
        )
        await db.commit()

    return UploadResponse(job_id=job_id)

