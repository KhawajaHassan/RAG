from __future__ import annotations

import asyncio

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from ..database import DB_PATH, update_job_status
from ..models import IndexStartResponse, StatusResponse
from ..pipelines.graph_indexing import run_indexing_job
from ..utils import require_openai_key


router = APIRouter(prefix="/api", tags=["index"])


async def _get_job(job_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        job = await (await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job_id not found")
        return job


async def _get_document_text(job_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute("SELECT content FROM documents WHERE job_id = ?", (job_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="No document stored for job_id")
        return row["content"] or ""


def _schedule_indexing(job_id: str, raw_text: str) -> None:
    async def runner() -> None:
        try:
            await run_indexing_job(job_id=job_id, raw_text=raw_text)
        except Exception as e:
            await update_job_status(
                job_id,
                status="failed",
                current_step="Failed",
                error=str(e),
                progress=1.0,
            )

    asyncio.create_task(runner())


@router.post("/index/{job_id}", response_model=IndexStartResponse)
async def start_indexing(job_id: str) -> IndexStartResponse:
    job = await _get_job(job_id)
    if job["status"] in {"running"}:
        return IndexStartResponse(job_id=job_id, started=False)

    raw_text = await _get_document_text(job_id)
    await update_job_status(job_id, status="queued", current_step="Queued", progress=0.01, error=None)
    # Schedule from the request event loop.
    _schedule_indexing(job_id, raw_text)
    return IndexStartResponse(job_id=job_id, started=True)


@router.get("/index/{job_id}/status", response_model=StatusResponse)
async def index_status(job_id: str) -> StatusResponse:
    job = await _get_job(job_id)
    stats = {}
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = await (await db.execute("SELECT * FROM graph_stats WHERE job_id = ?", (job_id,))).fetchone()
        if s:
            stats = {"entity_count": s["entity_count"], "edge_count": s["edge_count"], "community_count": s["community_count"]}

    return StatusResponse(
        job_id=job_id,
        status=job["status"] or "unknown",
        current_step=job["current_step"] or "",
        progress=float(job["progress"] or 0.0),
        error=job["error"],
        stats=stats,
    )

