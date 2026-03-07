from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import DB_PATH


router = APIRouter(prefix="/api", tags=["admin"])


@router.delete("/clear/{job_id}")
async def clear_job(job_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM evaluation_results WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM evaluation_questions WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM communities WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM entity_communities WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM relationships WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM entities WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM chunks WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM documents WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM graph_stats WHERE job_id = ?", (job_id,))
        cur = await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()

    # Remove chroma collection if exists
    try:
        from chromadb import Client
        from chromadb.config import Settings as ChromaSettings

        chroma = Client(ChromaSettings(is_persistent=True, persist_directory=str(settings.chroma_dir)))
        chroma.delete_collection(name=f"job_{job_id}")
    except Exception:
        pass

    return {"deleted": True, "job_id": job_id}

