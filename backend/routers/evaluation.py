from __future__ import annotations

import asyncio
import json

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from ..database import DB_PATH, update_job_status
from ..evaluation.question_generation import generate_questions
from ..evaluation.runner import run_evaluation_job
from ..models import (
    EvaluationEstimateRequest,
    EvaluationEstimateResponse,
    EvaluationGenerateResponse,
    EvaluationResultsResponse,
    EvaluationRunResponse,
)
from ..utils import require_openai_key


router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


async def _load_doc_preview(job_id: str, chars: int = 12000) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute("SELECT content FROM documents WHERE job_id = ?", (job_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="job_id not found")
        txt = row["content"] or ""
        return txt[:chars]


@router.post("/{job_id}/estimate", response_model=EvaluationEstimateResponse)
async def estimate_cost(job_id: str, req: EvaluationEstimateRequest) -> EvaluationEstimateResponse:
    # Simple requested estimate: ~$0.002 × 125 × 5 systems × 5 runs
    est = req.price_per_unit_usd * req.question_count * req.systems * req.runs
    return EvaluationEstimateResponse(estimated_cost_usd=float(est))


@router.post("/{job_id}/generate-questions", response_model=EvaluationGenerateResponse)
async def generate_questions_route(job_id: str) -> EvaluationGenerateResponse:
    preview = await _load_doc_preview(job_id)
    await update_job_status(job_id, current_step="Evaluation: Generating Questions", progress=0.02, error=None)
    count = await generate_questions(job_id=job_id, corpus_preview=preview)
    return EvaluationGenerateResponse(job_id=job_id, question_count=count)


def _schedule_eval(job_id: str) -> None:
    async def runner() -> None:
        try:
            await run_evaluation_job(job_id=job_id, repeats=5)
        except Exception as e:
            await update_job_status(job_id, status="failed", current_step="Evaluation: Failed", error=str(e), progress=1.0)

    asyncio.create_task(runner())


@router.post("/{job_id}/run", response_model=EvaluationRunResponse)
async def run_eval(job_id: str) -> EvaluationRunResponse:
    # Guard: require questions present
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute("SELECT COUNT(*) FROM evaluation_questions WHERE job_id = ?", (job_id,))).fetchone()
        if not row or int(row[0]) == 0:
            raise HTTPException(status_code=400, detail="No evaluation questions found. Generate questions first.")

    await update_job_status(job_id, status="queued", current_step="Evaluation: Queued", progress=0.01, error=None)
    _schedule_eval(job_id)
    return EvaluationRunResponse(job_id=job_id, started=True)


@router.get("/{job_id}/results", response_model=EvaluationResultsResponse)
async def eval_results(job_id: str) -> EvaluationResultsResponse:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT results_json FROM evaluation_results WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No evaluation results yet")
        try:
            obj = json.loads(row["results_json"] or "{}")
        except Exception:
            obj = {}
        return EvaluationResultsResponse(job_id=job_id, results=obj)

