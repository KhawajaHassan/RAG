from __future__ import annotations

import json
from typing import List, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException

from ..database import DB_PATH
from ..models import CommunityResponse, GraphEdge, GraphNode, GraphStats


router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph/{job_id}/stats", response_model=GraphStats)
async def graph_stats(job_id: str) -> GraphStats:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute("SELECT * FROM graph_stats WHERE job_id = ?", (job_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Graph not found for job_id")
        return GraphStats(
            entity_count=int(row["entity_count"] or 0),
            edge_count=int(row["edge_count"] or 0),
            community_count=int(row["community_count"] or 0),
        )


async def _community_map(job_id: str, level: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT name, community_id FROM entity_communities WHERE job_id = ? AND level = ?",
            (job_id, level),
        )).fetchall()
        return {r["name"]: r["community_id"] for r in rows}


@router.get("/graph/{job_id}/nodes", response_model=List[GraphNode])
async def graph_nodes(job_id: str, level: int = 0) -> List[GraphNode]:
    cmap = await _community_map(job_id, level)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT name, type, description, degree FROM entities WHERE job_id = ?",
            (job_id,),
        )).fetchall()
        return [
            GraphNode(
                id=r["name"],
                label=r["name"],
                type=r["type"],
                description=r["description"] or "",
                degree=float(r["degree"] or 0.0),
                community_level=level,
                community_id=cmap.get(r["name"]),
            )
            for r in rows
        ]


@router.get("/graph/{job_id}/edges", response_model=List[GraphEdge])
async def graph_edges(job_id: str) -> List[GraphEdge]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT source_name, target_name, description, weight FROM relationships WHERE job_id = ?",
            (job_id,),
        )).fetchall()
        return [
            GraphEdge(
                id=f"{r['source_name']}__{r['target_name']}",
                source=r["source_name"],
                target=r["target_name"],
                description=r["description"] or "",
                weight=float(r["weight"] or 1.0),
            )
            for r in rows
        ]


@router.get("/graph/{job_id}/community/{level}/{community_id}", response_model=CommunityResponse)
async def community(job_id: str, level: int, community_id: str) -> CommunityResponse:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT title, executive_summary, impact_severity, impact_explanation, findings_json FROM communities WHERE job_id = ? AND level = ? AND community_id = ?",
            (job_id, level, community_id),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Community not found")
        try:
            findings = json.loads(row["findings_json"] or "[]")
        except Exception:
            findings = []

        mem_rows = await (await db.execute(
            "SELECT name FROM entity_communities WHERE job_id = ? AND level = ? AND community_id = ?",
            (job_id, level, community_id),
        )).fetchall()
        members = [r["name"] for r in mem_rows]

        return CommunityResponse(
            job_id=job_id,
            level=level,
            community_id=community_id,
            title=row["title"] or community_id,
            executive_summary=row["executive_summary"] or "",
            impact_severity=float(row["impact_severity"] or 0.0),
            impact_explanation=row["impact_explanation"] or "",
            findings=[str(x) for x in findings],
            members=members,
        )

