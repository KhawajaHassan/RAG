from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers.evaluation import router as evaluation_router
from .routers.graph import router as graph_router
from .routers.index import router as index_router
from .routers.query import router as query_router
from .routers.upload import router as upload_router
from .routers.admin import router as admin_router


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()


app.include_router(upload_router)
app.include_router(index_router)
app.include_router(query_router)
app.include_router(graph_router)
app.include_router(evaluation_router)
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}

