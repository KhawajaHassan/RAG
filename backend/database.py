import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite

from .config import settings


DB_PATH = Path(settings.database_path)


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Jobs track uploads / indexing / evaluation
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TEXT,
                status TEXT,
                current_step TEXT,
                progress REAL,
                error TEXT
            );
            """
        )

        # Chunks of raw text
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                chunk_index INTEGER,
                content TEXT,
                start_char INTEGER,
                end_char INTEGER,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                job_id TEXT PRIMARY KEY,
                filename TEXT,
                content TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )

        # Graph entities and relationships
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                name TEXT,
                type TEXT,
                description TEXT,
                degree REAL DEFAULT 0,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_communities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                name TEXT,
                level INTEGER,
                community_id TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                source_name TEXT,
                target_name TEXT,
                description TEXT,
                weight REAL DEFAULT 1,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )

        # Communities and summaries
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS communities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                level INTEGER,
                community_id TEXT,
                title TEXT,
                executive_summary TEXT,
                impact_severity REAL,
                impact_explanation TEXT,
                findings_json TEXT
            );
            """
        )

        # Simple stats for live display
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_stats (
                job_id TEXT PRIMARY KEY,
                entity_count INTEGER,
                edge_count INTEGER,
                community_count INTEGER
            );
            """
        )

        # Evaluation artefacts
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                persona TEXT,
                task TEXT,
                question TEXT
            );
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                results_json TEXT
            );
            """
        )

        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def update_job_status(
    job_id: str,
    *,
    status: Optional[str] = None,
    current_step: Optional[str] = None,
    progress: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        fields: Dict[str, Any] = {}
        if status is not None:
            fields["status"] = status
        if current_step is not None:
            fields["current_step"] = current_step
        if progress is not None:
            fields["progress"] = progress
        if error is not None:
            fields["error"] = error

        if not fields:
            return

        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        fields["job_id"] = job_id

        await db.execute(
            f"UPDATE jobs SET {assignments} WHERE id = :job_id", fields
        )
        await db.commit()


def init_db_sync() -> None:
    asyncio.run(init_db())

