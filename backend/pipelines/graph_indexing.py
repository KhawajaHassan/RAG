from __future__ import annotations

import json
import math
import pickle
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
import networkx as nx
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import settings
from ..database import DB_PATH, update_job_status
from ..llm import chat, chat_json, embed_many
from ..utils import now_iso


SAMPLE_DATA_DIR = Path(__file__).resolve().parents[1] / "sample_data"
GRAPH_PICKLE_DIR = Path(__file__).resolve().parents[1] / "graph_pickles"


@dataclass
class ExtractedChunk:
    chunk_index: int
    content: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]


def _safe_entity_type(t: str) -> str:
    t = (t or "").upper()
    return t if t in {"PERSON", "ORG", "LOCATION", "CONCEPT", "EVENT"} else "CONCEPT"


def _merge_node(g: nx.DiGraph, name: str, ntype: str, desc: str) -> None:
    if g.has_node(name):
        prev = g.nodes[name].get("description", "")
        merged = (prev + "\n" + desc).strip() if desc else prev
        g.nodes[name]["description"] = merged
        g.nodes[name]["type"] = g.nodes[name].get("type") or ntype
    else:
        g.add_node(name, type=ntype, description=desc or "")


def _merge_edge(g: nx.DiGraph, s: str, t: str, desc: str, strength: float) -> None:
    if g.has_edge(s, t):
        g[s][t]["weight"] = float(g[s][t].get("weight", 1.0)) + float(strength or 1.0)
        if desc:
            prev = g[s][t].get("description", "")
            g[s][t]["description"] = (prev + "\n" + desc).strip() if prev else desc
    else:
        g.add_edge(s, t, weight=float(strength or 1.0), description=desc or "")


def _extract_json(chunk_text: str) -> Dict[str, Any]:
  prompt = (
      "Extract entities and relationships from the text.\n"
      "Return ONLY a JSON object with keys:\n"
      "entities: [{name, type, description}] where type in PERSON, ORG, LOCATION, CONCEPT, EVENT\n"
      "relationships: [{source, target, description, strength}] where strength is 1-10\n\n"
      "Text:\n"
      f"{chunk_text}"
  )
  obj = chat_json(
      [
          {
              "role": "system",
              "content": "You extract structured information for building knowledge graphs. Respond with JSON only.",
          },
          {"role": "user", "content": prompt},
      ]
  )
  obj.setdefault("entities", [])
  obj.setdefault("relationships", [])
  return obj


def _reflection_loop(chunk_text: str, base: Dict[str, Any], max_loops: int = 2) -> Dict[str, Any]:
    cur = base
    for _ in range(max_loops):
        prompt = (
            "You previously extracted entities/relationships from a text.\n"
            "Check if anything important is missing. If yes, return JSON with keys:\n"
            "missed (boolean), add_entities (list), add_relationships (list).\n"
            "If missed is false, set add_* to empty lists.\n\n"
            f"Text:\n{chunk_text}\n\nCurrent extraction:\n{json.dumps(cur)[:8000]}"
        )
        obj = chat_json(
            [
                {"role": "system", "content": "You validate and improve extractions. Respond with JSON only."},
                {"role": "user", "content": prompt},
            ]
        )

        if not obj.get("missed"):
            break

        cur.setdefault("entities", [])
        cur.setdefault("relationships", [])
        for e in obj.get("add_entities") or []:
            cur["entities"].append(e)
        for r in obj.get("add_relationships") or []:
            cur["relationships"].append(r)

    return cur


async def _store_chunks(job_id: str, chunks: List[Dict[str, Any]]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM chunks WHERE job_id = ?", (job_id,))
        for c in chunks:
            await db.execute(
                "INSERT INTO chunks (job_id, chunk_index, content, start_char, end_char) VALUES (?, ?, ?, ?, ?)",
                (job_id, c["chunk_index"], c["content"], c.get("start_char", 0), c.get("end_char", 0)),
            )
        await db.commit()


async def _store_graph(job_id: str, g: nx.DiGraph) -> None:
    GRAPH_PICKLE_DIR.mkdir(parents=True, exist_ok=True)
    pkl_path = GRAPH_PICKLE_DIR / f"{job_id}.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(g, f)

    # Store nodes/edges into SQLite for fast API access
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM entities WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM relationships WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM entity_communities WHERE job_id = ?", (job_id,))

        deg = nx.degree_centrality(g.to_undirected())
        for name, attrs in g.nodes(data=True):
            await db.execute(
                "INSERT INTO entities (job_id, name, type, description, degree) VALUES (?, ?, ?, ?, ?)",
                (job_id, name, attrs.get("type", "CONCEPT"), attrs.get("description", ""), float(deg.get(name, 0.0))),
            )

        for s, t, attrs in g.edges(data=True):
            await db.execute(
                "INSERT INTO relationships (job_id, source_name, target_name, description, weight) VALUES (?, ?, ?, ?, ?)",
                (job_id, s, t, attrs.get("description", ""), float(attrs.get("weight", 1.0))),
            )

        await db.execute(
            "INSERT OR REPLACE INTO graph_stats (job_id, entity_count, edge_count, community_count) VALUES (?, ?, ?, ?)",
            (job_id, g.number_of_nodes(), g.number_of_edges(), 0),
        )
        await db.commit()


def _nx_to_igraph(g: nx.Graph):
    import igraph as ig

    nodes = list(g.nodes())
    idx = {n: i for i, n in enumerate(nodes)}
    edges = [(idx[s], idx[t]) for s, t in g.edges()]
    weights = [float(g[s][t].get("weight", 1.0)) for s, t in g.edges()]

    ig_g = ig.Graph(n=len(nodes), edges=edges, directed=False)
    ig_g.vs["name"] = nodes
    ig_g.es["weight"] = weights
    return ig_g


def _run_leiden_levels(g: nx.DiGraph) -> Dict[int, Dict[str, str]]:
    """
    Returns: level -> node_name -> community_id
    Levels are coarse-to-fine labels C0..C3 (0..3).
    """
    import leidenalg

    ug = g.to_undirected()
    ig_g = _nx_to_igraph(ug)

    memberships: Dict[int, Dict[str, str]] = {}
    # Coarse-to-fine by increasing resolution parameter
    resolutions = [0.2, 0.6, 1.2, 2.0]
    for level, res in enumerate(resolutions):
        part = leidenalg.find_partition(
            ig_g,
            leidenalg.RBConfigurationVertexPartition,
            weights="weight",
            resolution_parameter=res,
        )
        m = {}
        for v_idx, comm in enumerate(part.membership):
            name = ig_g.vs[v_idx]["name"]
            m[name] = f"C{level}_{comm}"
        memberships[level] = m

    return memberships


def _community_nodes(membership: Dict[str, str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)
    for n, cid in membership.items():
        groups[cid].append(n)
    return groups


def _prioritize_nodes_for_context(g: nx.DiGraph, nodes: List[str], limit: int = 50) -> List[str]:
    deg = dict(g.degree())
    nodes = sorted(nodes, key=lambda n: deg.get(n, 0), reverse=True)
    return nodes[:limit]


def _summarize_community(
    *,
    level: int,
    community_id: str,
    nodes: List[str],
    g: nx.DiGraph,
    child_summaries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    prioritized = _prioritize_nodes_for_context(g, nodes, limit=60)
    node_lines = []
    for n in prioritized:
        desc = (g.nodes[n].get("description", "") or "")[:500]
        node_lines.append(f"- {n} ({g.nodes[n].get('type','CONCEPT')}): {desc}")
    edges = []
    for s, t in g.edges():
        if s in set(prioritized) and t in set(prioritized):
            w = float(g[s][t].get("weight", 1.0))
            d = (g[s][t].get("description", "") or "")[:240]
            edges.append(f"- {s} -> {t} (w={w:.1f}): {d}")
        if len(edges) >= 120:
            break

    ctx = "\n".join(node_lines) + "\n\nEdges:\n" + "\n".join(edges)
    child = ""
    if child_summaries:
        child = "Sub-community summaries:\n" + json.dumps(child_summaries)[:6000]

    prompt = (
        "Generate a structured community summary JSON with keys:\n"
        "{title, executive_summary, impact_severity (0-10), impact_explanation, findings (5-10 strings)}.\n"
        "Base it on the provided nodes/edges context. Be specific.\n"
        "Respond with JSON only.\n\n"
        f"Community: {community_id} (level {level})\n\n"
        f"{child}\n\nContext:\n{ctx}"
    )
    obj = chat_json(
        [
            {
                "role": "system",
                "content": "You create concise, structured summaries for knowledge graph communities. Respond with JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
    )

    findings = obj.get("findings") or []
    if not isinstance(findings, list):
        findings = []

    return {
        "job_id": None,
        "level": level,
        "community_id": community_id,
        "title": (obj.get("title") or f"{community_id}").strip(),
        "executive_summary": (obj.get("executive_summary") or "").strip(),
        "impact_severity": float(obj.get("impact_severity") or 0.0),
        "impact_explanation": (obj.get("impact_explanation") or "").strip(),
        "findings": [str(x).strip() for x in findings if str(x).strip()],
    }


async def _store_communities(job_id: str, summaries: List[Dict[str, Any]], membership: Dict[int, Dict[str, str]]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM communities WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM entity_communities WHERE job_id = ?", (job_id,))

        for level, m in membership.items():
            for node, cid in m.items():
                await db.execute(
                    "INSERT INTO entity_communities (job_id, name, level, community_id) VALUES (?, ?, ?, ?)",
                    (job_id, node, int(level), cid),
                )

        for s in summaries:
            await db.execute(
                """
                INSERT INTO communities (
                    job_id, level, community_id, title, executive_summary,
                    impact_severity, impact_explanation, findings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    int(s["level"]),
                    s["community_id"],
                    s["title"],
                    s["executive_summary"],
                    float(s["impact_severity"]),
                    s["impact_explanation"],
                    json.dumps(s["findings"]),
                ),
            )

        # Stats: count communities at C0 by default
        c0_ids = set(membership.get(0, {}).values())
        row_e = await (await db.execute("SELECT COUNT(*) FROM entities WHERE job_id = ?", (job_id,))).fetchone()
        row_r = await (await db.execute("SELECT COUNT(*) FROM relationships WHERE job_id = ?", (job_id,))).fetchone()
        await db.execute(
            "INSERT OR REPLACE INTO graph_stats (job_id, entity_count, edge_count, community_count) VALUES (?, ?, ?, ?)",
            (job_id, row_e[0], row_r[0], len(c0_ids)),
        )
        await db.commit()


async def _index_into_chroma(job_id: str, chunks: List[Dict[str, Any]]) -> None:
    from chromadb import Client
    from chromadb.config import Settings as ChromaSettings

    chroma = Client(
        ChromaSettings(is_persistent=True, persist_directory=str(settings.chroma_dir))
    )
    col = chroma.get_or_create_collection(name=f"job_{job_id}")

    # Clear existing
    try:
        col.delete(where={})
    except Exception:
        pass

    # Embed in small batches via Ollama
    batch_size = 32
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [b["content"] for b in batch]
        vectors = embed_many(texts)
        ids = [f"{job_id}_chunk_{b['chunk_index']}" for b in batch]
        metas = [
            {"chunk_index": b["chunk_index"], "start_char": b.get("start_char", 0), "end_char": b.get("end_char", 0)}
            for b in batch
        ]
        col.add(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)


async def run_indexing_job(*, job_id: str, raw_text: str) -> None:
    await update_job_status(job_id, status="running", current_step="Chunking", progress=0.05, error=None)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    docs = splitter.create_documents([raw_text])
    chunks: List[Dict[str, Any]] = []
    cursor = 0
    for idx, d in enumerate(docs):
        txt = d.page_content
        start = cursor
        end = cursor + len(txt)
        cursor = end
        chunks.append(
            {"chunk_index": idx, "content": txt, "start_char": start, "end_char": end}
        )

    await _store_chunks(job_id, chunks)

    await update_job_status(job_id, current_step="Embedding", progress=0.15)
    await _index_into_chroma(job_id, chunks)

    await update_job_status(job_id, current_step="Extracting", progress=0.35)
    g = nx.DiGraph()

    extracted_ok = 0
    for i, c in enumerate(chunks):
        # Progress across extraction stage (35% -> 60%)
        stage_p = 0.35 + 0.25 * (i / max(1, len(chunks)))
        await update_job_status(job_id, progress=stage_p)

        try:
            base = _extract_json(c["content"])
            improved = _reflection_loop(c["content"], base, max_loops=2)
        except Exception:
            # Key rule: skip failures, never crash pipeline
            continue

        ents = improved.get("entities") or []
        rels = improved.get("relationships") or []

        for e in ents:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            _merge_node(g, name, _safe_entity_type(e.get("type") or "CONCEPT"), (e.get("description") or "").strip())

        for r in rels:
            s = (r.get("source") or "").strip()
            t = (r.get("target") or "").strip()
            if not s or not t:
                continue
            if not g.has_node(s):
                _merge_node(g, s, "CONCEPT", "")
            if not g.has_node(t):
                _merge_node(g, t, "CONCEPT", "")
            strength = float(r.get("strength") or 1.0)
            strength = max(1.0, min(10.0, strength))
            _merge_edge(g, s, t, (r.get("description") or "").strip(), strength)

        extracted_ok += 1

    await update_job_status(job_id, current_step="Building Graph", progress=0.65)
    await _store_graph(job_id, g)

    await update_job_status(job_id, current_step="Communities", progress=0.72)
    membership = _run_leiden_levels(g) if g.number_of_nodes() > 0 else {0: {}, 1: {}, 2: {}, 3: {}}

    await update_job_status(job_id, current_step="Summarizing", progress=0.82)
    # Summarize communities bottom-up (C3 -> C0)
    summaries: List[Dict[str, Any]] = []
    summaries_by_level: Dict[int, Dict[str, Dict[str, Any]]] = {0: {}, 1: {}, 2: {}, 3: {}}
    for level in [3, 2, 1, 0]:
        groups = _community_nodes(membership.get(level, {}))
        items = list(groups.items())
        random.shuffle(items)
        for j, (cid, nodes) in enumerate(items):
            # Summarization progress (82% -> 98%)
            p = 0.82 + 0.16 * ((j + 1) / max(1, len(items)))
            await update_job_status(job_id, progress=p)

            child = None
            if level < 3:
                # Provide one level deeper summaries as context
                child_level = level + 1
                child = []
                for n in nodes[:80]:
                    cchild = membership.get(child_level, {}).get(n)
                    if cchild and cchild in summaries_by_level[child_level]:
                        child.append(summaries_by_level[child_level][cchild])
                # Keep small
                child = child[:10]

            try:
                s = _summarize_community(
                    level=level,
                    community_id=cid,
                    nodes=nodes,
                    g=g,
                    child_summaries=child,
                )
            except Exception:
                continue
            summaries.append(s)
            summaries_by_level[level][cid] = s

    await _store_communities(job_id, summaries, membership)
    await update_job_status(job_id, status="completed", current_step="Done", progress=1.0)
