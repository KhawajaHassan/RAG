from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Tuple

import aiosqlite
import networkx as nx

from ..config import settings
from ..database import DB_PATH
from ..llm import chat, chat_json


async def _load_community_summaries(job_id: str, level: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT level, community_id, title, executive_summary, impact_severity, impact_explanation, findings_json FROM communities WHERE job_id = ? AND level = ?",
            (job_id, level),
        )).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                findings = json.loads(r["findings_json"] or "[]")
            except Exception:
                findings = []
            out.append(
                {
                    "level": r["level"],
                    "community_id": r["community_id"],
                    "title": r["title"],
                    "executive_summary": r["executive_summary"],
                    "impact_severity": r["impact_severity"],
                    "impact_explanation": r["impact_explanation"],
                    "findings": findings,
                }
            )
        return out


def _batch_json(items: List[Dict[str, Any]], approx_chars: int = 14000) -> List[str]:
    batches: List[str] = []
    buf: List[str] = []
    size = 0
    for it in items:
        s = json.dumps(it, ensure_ascii=False)
        size += len(s)
        buf.append(s)
        if size >= approx_chars:
            batches.append("[\n" + ",\n".join(buf) + "\n]")
            buf = []
            size = 0
    if buf:
        batches.append("[\n" + ",\n".join(buf) + "\n]")
    return batches


async def run_graph_global_search(*, job_id: str, question: str, level: int = 0) -> Dict[str, Any]:
    summaries = await _load_community_summaries(job_id, level)
    random.shuffle(summaries)
    batches = _batch_json(summaries)

    map_outputs: List[Tuple[int, str, int]] = []
    for i, b in enumerate(batches):
        prompt = (
            "Use the provided community summaries (JSON list) to answer the question.\n"
            "Return JSON {partial_answer, helpfulness_score 0-100}. If irrelevant, score 0.\n\n"
            f"Question: {question}\n\nSummaries:\n{b}"
        )
        try:
            obj = chat_json(
                [
                    {
                        "role": "system",
                        "content": "You are a research assistant doing global sensemaking. Respond with JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            ans = (obj.get("partial_answer") or "").strip()
            score = int(obj.get("helpfulness_score") or 0)
        except Exception:
            ans = ""
            score = 0
        if ans and score > 0:
            map_outputs.append((i, ans, max(0, min(100, score))))

    map_outputs.sort(key=lambda t: t[2], reverse=True)

    # Reduce by concatenating into a final answer
    char_budget = settings.max_context_tokens * 4
    ctx_parts: List[str] = []
    used = 0
    for i, ans, score in map_outputs:
        part = f"[batch={i} score={score}]\n{ans}"
        if used + len(part) > char_budget:
            break
        ctx_parts.append(part)
        used += len(part)

    final_prompt = (
        "Synthesize a final answer from the scored partial answers.\n"
        "If uncertain, state assumptions and propose what to verify.\n\n"
        f"Question: {question}\n\nPartial answers:\n{'\n\n'.join(ctx_parts)}"
    )

    answer = chat(
        [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": final_prompt},
        ]
    )

    return {
        "mode": "graph_global",
        "answer": answer,
        "sources": [{"batch_index": i, "score": s} for (i, _, s) in map_outputs[:10]],
    }


async def _load_graph(job_id: str) -> nx.DiGraph:
    # Prefer reconstructing from DB tables to avoid pickle I/O in API path
    g = nx.DiGraph()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        nodes = await (await db.execute(
            "SELECT name, type, description FROM entities WHERE job_id = ?",
            (job_id,),
        )).fetchall()
        for n in nodes:
            g.add_node(n["name"], type=n["type"], description=n["description"])
        edges = await (await db.execute(
            "SELECT source_name, target_name, description, weight FROM relationships WHERE job_id = ?",
            (job_id,),
        )).fetchall()
        for e in edges:
            g.add_edge(e["source_name"], e["target_name"], description=e["description"], weight=float(e["weight"]))
    return g


def _bfs_hierarchy_text(g: nx.DiGraph, root: str, max_hops: int) -> str:
    lines: List[str] = []
    visited = {root}
    frontier = [(root, 0)]
    while frontier:
        node, depth = frontier.pop(0)
        indent = "  " * depth
        ntype = g.nodes[node].get("type", "CONCEPT")
        desc = (g.nodes[node].get("description", "") or "")[:240]
        lines.append(f"{indent}- {node} ({ntype}): {desc}")
        if depth >= max_hops:
            continue
        nbrs = list(g.successors(node)) + list(g.predecessors(node))
        for nb in nbrs[:25]:
            if nb in visited:
                continue
            visited.add(nb)
            frontier.append((nb, depth + 1))
    return "\n".join(lines)


async def run_graph_local_search(*, job_id: str, question: str, hops: int = 2) -> Dict[str, Any]:
    g = await _load_graph(job_id)
    if g.number_of_nodes() == 0:
        return {"mode": "graph_local", "answer": "No graph is available for this job yet.", "sources": []}

    # Extract query entities via GPT (spaCy can be added, but GPT keeps deps lighter)
    extract_prompt = (
        "Extract key entity strings from the question.\n"
        "Return JSON {entities: [string,...]} with 3-10 items.\n\n"
        f"Question: {question}"
    )
    try:
        obj = chat_json(
            [
                {
                    "role": "system",
                    "content": "You extract entity strings from questions. Respond with JSON only.",
                },
                {"role": "user", "content": extract_prompt},
            ]
        )
        ents = [str(e).strip() for e in (obj.get("entities") or []) if str(e).strip()]
    except Exception:
        ents = []

    # Match to graph nodes (simple contains match)
    node_names = list(g.nodes())
    matched: List[str] = []
    lowered = {n.lower(): n for n in node_names}
    for e in ents:
        key = e.lower()
        if key in lowered:
            matched.append(lowered[key])
            continue
        for n in node_names:
            if key in n.lower():
                matched.append(n)
                break

    matched = list(dict.fromkeys(matched))[:3]
    if not matched:
        matched = sorted(node_names, key=lambda n: g.degree(n), reverse=True)[:1]

    # Build ego context around first match
    root = matched[0]
    ego = nx.ego_graph(g.to_undirected(), root, radius=max(1, min(2, hops)))
    sub = g.subgraph(ego.nodes()).copy()

    hierarchy = _bfs_hierarchy_text(sub, root, max_hops=max(1, min(2, hops)))
    prompt = (
        "Answer the question using ONLY the provided local knowledge graph neighborhood description.\n"
        "If the neighborhood is insufficient, say what graph nodes would be needed.\n\n"
        f"Question: {question}\n\nNeighborhood:\n{hierarchy}"
    )
    answer = chat(
        [
            {
                "role": "system",
                "content": "You are a careful assistant reasoning locally from a graph neighborhood.",
            },
            {"role": "user", "content": prompt},
        ]
    )

    return {
        "mode": "graph_local",
        "answer": answer,
        "sources": [{"root": root, "nodes": list(sub.nodes())[:200]}],
        "ego_graph": {
            "root": root,
            "nodes": [{"id": n, "label": n, "type": sub.nodes[n].get("type", "CONCEPT")} for n in sub.nodes()],
            "edges": [{"source": s, "target": t, "weight": float(sub[s][t].get("weight", 1.0))} for s, t in sub.edges()],
        },
    }

