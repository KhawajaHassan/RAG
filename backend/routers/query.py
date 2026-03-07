from __future__ import annotations

import time
from typing import List

import aiosqlite
from fastapi import APIRouter, HTTPException

from ..database import DB_PATH
from ..models import QueryRequest, QueryResponse, QueryResult
from ..pipelines.direct_llm import run_direct_llm
from ..pipelines.graph_search import run_graph_global_search, run_graph_local_search
from ..pipelines.summary_rag import run_summary_rag
from ..pipelines.vector_rag import run_vector_rag


router = APIRouter(prefix="/api", tags=["query"])


async def _load_chunks(job_id: str, limit: int = 2000) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT chunk_index, content, start_char, end_char FROM chunks WHERE job_id = ? ORDER BY chunk_index ASC LIMIT ?",
            (job_id, limit),
        )).fetchall()
        return [dict(r) for r in rows]


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    modes = [req.mode] if req.mode != "all" else ["direct_llm", "vector_rag", "summary_rag", "graph_global", "graph_local"]
    results: List[QueryResult] = []

    raw_chunks = await _load_chunks(req.job_id)
    if not raw_chunks and any(m in {"summary_rag", "graph_global", "graph_local", "vector_rag"} for m in modes):
        raise HTTPException(status_code=400, detail="No indexed data found for job_id. Run indexing first.")

    for m in modes:
        start = time.time()
        if m == "direct_llm":
            out = await run_direct_llm(question=req.question)
        elif m == "vector_rag":
            out = await run_vector_rag(job_id=req.job_id, question=req.question)
        elif m == "summary_rag":
            out = await run_summary_rag(question=req.question, raw_chunks=raw_chunks)
        elif m == "graph_global":
            out = await run_graph_global_search(job_id=req.job_id, question=req.question, level=0)
        elif m == "graph_local":
            out = await run_graph_local_search(job_id=req.job_id, question=req.question, hops=2)
        else:
            continue

        latency_ms = int((time.time() - start) * 1000)
        results.append(
            QueryResult(
                mode=out["mode"],
                answer=out.get("answer", ""),
                latency_ms=latency_ms,
                sources=(out.get("sources", []) or []) + (
                    [{"ego_graph": out.get("ego_graph")}] if out.get("ego_graph") else []
                ),
            )
        )

    return QueryResponse(job_id=req.job_id, question=req.question, results=results)

