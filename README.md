# Multi-Document Reasoning with Graph-Augmented RAG

Full-stack B.Tech final-year project app for **Multi-Document Reasoning with Graph-Augmented RAG**.

## Architecture

- **Frontend**: React (Vite) + TailwindCSS v4 + ReactFlow + Recharts + Zustand + TanStack Query + Axios + react-hot-toast  
- **Backend**: FastAPI + SQLite (aiosqlite) + BackgroundTasks job runner  
- **LLM**: OpenAI **GPT-4o-mini** (all LLM tasks)  
- **Embeddings**: OpenAI **text-embedding-3-small**  
- **Vector store**: ChromaDB (persistent)
- **Graph**: NetworkX (DiGraph) + Leiden community detection (leidenalg + igraph)
- **Chunking**: LangChain `RecursiveCharacterTextSplitter` (`chunk_size=600`, `overlap=100`)

**OpenAI key is never stored server-side**. The frontend sends it on every request via the `X-OpenAI-Key` header.

## Backend pipelines

### Pipeline A — Vector RAG

1. Embed the query (`text-embedding-3-small`)
2. Retrieve top-k chunks from ChromaDB
3. Send context + question to `gpt-4o-mini`

### Pipeline A2 — Text Summarization RAG (Map-Reduce)

1. Map: batch raw chunks → `gpt-4o-mini` returns JSON `{partial_answer, helpfulness_score}`
2. Filter score=0
3. Reduce: sort by score and synthesize final answer

### Pipeline B — Graph indexing (offline after upload)

1. Chunk docs
2. Per chunk: extract entities + relationships as JSON (with up to 2 reflection loops)
3. Build a NetworkX DiGraph; merge dup nodes/edges
4. Leiden community detection at 4 levels (C0–C3)
5. Community summaries (bottom-up) using `gpt-4o-mini`
6. Persist in SQLite (entities, edges, communities, membership)

### Pipeline B — Global search

Map-reduce over **community summaries** (C0 by default), then synthesize.

### Pipeline B — Local search

Extract query entities (LLM), match nodes, build a K-hop neighborhood, convert to a BFS hierarchy text, then answer.

## Evaluation

- Generate **125 questions**: 5 personas × 5 tasks × 5 questions
- Run **5 systems**: `direct_llm` baseline + Vector RAG + Summary RAG + Graph Global + Graph Local
- LLM-as-judge: pairwise comparisons on 4 criteria, repeated 5 times
- Claim metrics: extract factual claims, count unique claims, cluster by ROUGE-L distance (agglomerative clustering)

Cost estimate is shown in the UI before running evaluation.

## API

- `POST /api/upload` → `{ job_id }`
- `POST /api/index/{job_id}` → starts background indexing
- `GET /api/index/{job_id}/status` → step + progress + stats
- `POST /api/query` → `{question, mode, job_id}` → answers + latency + sources
- `GET /api/graph/{job_id}/nodes?level=0..3`
- `GET /api/graph/{job_id}/edges`
- `GET /api/graph/{job_id}/stats`
- `GET /api/graph/{job_id}/community/{level}/{id}`
- `POST /api/evaluation/{job_id}/estimate`
- `POST /api/evaluation/{job_id}/generate-questions`
- `POST /api/evaluation/{job_id}/run`
- `GET /api/evaluation/{job_id}/results`
- `DELETE /api/clear/{job_id}` → clear stored data for a job

## Setup & Run

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the app at `http://localhost:5173`.

## Demo data

Use `backend/sample_data/public_domain_demo.txt` as a quick upload-and-index demo.

