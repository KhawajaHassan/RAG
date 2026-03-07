from __future__ import annotations

import asyncio
import itertools
import json
import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import aiosqlite
from rouge_score import rouge_scorer
from sklearn.cluster import AgglomerativeClustering

from ..config import settings
from ..database import DB_PATH, update_job_status
from ..llm import chat, chat_json
from ..pipelines.direct_llm import run_direct_llm
from ..pipelines.graph_search import run_graph_global_search, run_graph_local_search
from ..pipelines.summary_rag import run_summary_rag
from ..pipelines.vector_rag import run_vector_rag


SYSTEMS = ["direct_llm", "vector_rag", "summary_rag", "graph_global", "graph_local"]
CRITERIA = ["Comprehensiveness", "Diversity", "Empowerment", "Directness"]


async def load_questions(job_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT persona, task, question FROM evaluation_questions WHERE job_id = ? ORDER BY id ASC",
            (job_id,),
        )).fetchall()
        return [dict(r) for r in rows]


async def load_chunks(job_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT chunk_index, content, start_char, end_char FROM chunks WHERE job_id = ? ORDER BY chunk_index ASC",
            (job_id,),
        )).fetchall()
        return [dict(r) for r in rows]


async def generate_system_answer(job_id: str, question: str, system: str, raw_chunks: List[Dict[str, Any]]) -> str:
    if system == "direct_llm":
        out = await run_direct_llm(question=question)
    elif system == "vector_rag":
        out = await run_vector_rag(job_id=job_id, question=question)
    elif system == "summary_rag":
        out = await run_summary_rag(question=question, raw_chunks=raw_chunks)
    elif system == "graph_global":
        out = await run_graph_global_search(job_id=job_id, question=question, level=0)
    elif system == "graph_local":
        out = await run_graph_local_search(job_id=job_id, question=question, hops=2)
    else:
        out = {"answer": ""}
    return out.get("answer") or ""


def judge_pair(*, question: str, answer_a: str, answer_b: str, criterion: str) -> str:
    prompt = (
        "You are an impartial judge comparing two answers to the same question.\n"
        f"Criterion: {criterion}\n"
        "Choose the better answer for this criterion.\n"
        "Return JSON: {winner: \"A\"|\"B\"|\"TIE\", rationale: string}.\n\n"
        f"Question:\n{question}\n\nAnswer A:\n{answer_a}\n\nAnswer B:\n{answer_b}"
    )
    obj = chat_json(
        [
            {
                "role": "system",
                "content": "You are an impartial judge comparing two answers. Respond with JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
    )
    w = (obj.get("winner") or "TIE").upper()
    return w if w in {"A", "B", "TIE"} else "TIE"


def extract_claims(*, answer: str) -> List[str]:
    prompt = (
        "Extract factual claims from the answer.\n"
        "Return JSON {claims: [string,...]} with each claim short and atomic.\n"
        "Exclude opinions or purely generic advice.\n\n"
        f"Answer:\n{answer}"
    )
    obj = chat_json(
        [
            {
                "role": "system",
                "content": "You extract factual claims from answers. Respond with JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
    )
    claims = [str(c).strip() for c in (obj.get("claims") or []) if str(c).strip()]
    # De-dupe
    out = []
    seen = set()
    for c in claims:
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


def claim_cluster_stats(claims: List[str]) -> Dict[str, Any]:
    if not claims:
        return {"unique_claims": 0, "clusters": 0}

    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    n = len(claims)
    # Distance matrix (condensed not required since sklearn supports precomputed with full matrix)
    dist = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            sim = scorer.score(claims[i], claims[j])["rougeL"].fmeasure
            d = 1.0 - float(sim)
            dist[i][j] = d
            dist[j][i] = d

    # Agglomerative clustering on distances
    # Threshold tuned for ROUGE-L; lower => more clusters
    clustering = AgglomerativeClustering(
        metric="precomputed",
        linkage="average",
        distance_threshold=0.55,
        n_clusters=None,
    )
    labels = clustering.fit_predict(dist)
    clusters = len(set(labels))
    return {"unique_claims": n, "clusters": clusters}


async def run_evaluation_job(*, job_id: str, repeats: int = 5) -> Dict[str, Any]:
    await update_job_status(job_id, status="running", current_step="Evaluation: Loading", progress=0.01, error=None)

    questions = await load_questions(job_id)
    raw_chunks = await load_chunks(job_id)

    # Generate answers
    answers: Dict[str, List[str]] = {s: [] for s in SYSTEMS}
    for i, q in enumerate(questions):
        await update_job_status(job_id, current_step="Evaluation: Answering", progress=0.05 + 0.35 * (i / max(1, len(questions))))
        question = q["question"]
        for s in SYSTEMS:
            try:
                ans = await generate_system_answer(job_id, question, s, raw_chunks)
            except Exception:
                ans = ""
            answers[s].append(ans)

    await update_job_status(job_id, current_step="Evaluation: Judging", progress=0.45)

    # Pairwise comparisons per criterion, repeated
    win_counts = {c: defaultdict(int) for c in CRITERIA}  # criterion -> (A,B) key -> wins for A (A over B)
    comparisons = list(itertools.combinations(SYSTEMS, 2))
    total_trials = len(questions) * len(comparisons) * len(CRITERIA) * repeats
    done = 0

    for qi, q in enumerate(questions):
        question = q["question"]
        for (a, b) in comparisons:
            ans_a = answers[a][qi]
            ans_b = answers[b][qi]
            for c in CRITERIA:
                for _ in range(repeats):
                    w = judge_pair(question=question, answer_a=ans_a, answer_b=ans_b, criterion=c)
                    if w == "A":
                        win_counts[c][(a, b)] += 1
                    elif w == "B":
                        win_counts[c][(b, a)] += 1
                    done += 1
                    if done % 20 == 0:
                        await update_job_status(job_id, progress=0.45 + 0.45 * (done / max(1, total_trials)))

    # Normalize to win rates matrix per criterion
    win_rates: Dict[str, Dict[str, Dict[str, float]]] = {c: {s: {t: 0.0 for t in SYSTEMS} for s in SYSTEMS} for c in CRITERIA}
    for c in CRITERIA:
        for a in SYSTEMS:
            win_rates[c][a][a] = 0.5
        for (a, b) in comparisons:
            a_wins = win_counts[c][(a, b)]
            b_wins = win_counts[c][(b, a)]
            denom = a_wins + b_wins
            if denom == 0:
                wa = wb = 0.5
            else:
                wa = a_wins / denom
                wb = b_wins / denom
            win_rates[c][a][b] = wa
            win_rates[c][b][a] = wb

    await update_job_status(job_id, current_step="Evaluation: Claims", progress=0.92)
    # Claim metrics: average claims/clusters per system
    claim_stats: Dict[str, Dict[str, float]] = {}
    for s in SYSTEMS:
        all_unique = []
        all_clusters = []
        for ans in answers[s]:
            try:
                claims = extract_claims(answer=ans)
            except Exception:
                claims = []
            st = claim_cluster_stats(claims)
            all_unique.append(st["unique_claims"])
            all_clusters.append(st["clusters"])
        claim_stats[s] = {
            "avg_unique_claims": float(sum(all_unique) / max(1, len(all_unique))),
            "avg_clusters": float(sum(all_clusters) / max(1, len(all_clusters))),
        }

    results = {
        "systems": SYSTEMS,
        "criteria": CRITERIA,
        "win_rates": win_rates,
        "claim_stats": claim_stats,
        "questions": questions,
    }

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM evaluation_results WHERE job_id = ?", (job_id,))
        await db.execute(
            "INSERT INTO evaluation_results (job_id, results_json) VALUES (?, ?)",
            (job_id, json.dumps(results)),
        )
        await db.commit()

    await update_job_status(job_id, status="completed", current_step="Evaluation: Done", progress=1.0)
    return results

