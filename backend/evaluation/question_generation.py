from __future__ import annotations

import json
from typing import Any, Dict, List

import aiosqlite

from ..config import settings
from ..database import DB_PATH
from ..llm import chat_json


QUESTION_GEN_PROMPT = """
You will generate evaluation questions for a multi-document reasoning system.

Create 5 personas. For each persona, create 5 tasks. For each task, create 5 questions.
Total questions = 125.

All questions must require global, multi-document reasoning across the full corpus (sensemaking, synthesis, trade-offs).
Avoid trivia and avoid questions answerable from a single paragraph.

Return JSON:
{
  "personas": [
    {
      "persona": "...",
      "tasks": [
        {
          "task": "...",
          "questions": ["...", "..."]
        }
      ]
    }
  ]
}
"""


async def generate_questions(*, job_id: str, corpus_preview: str) -> int:
    obj = chat_json(
        [
            {"role": "system", "content": "You design rigorous evaluation questions. Respond with JSON only."},
            {"role": "user", "content": QUESTION_GEN_PROMPT + "\n\nCorpus preview:\n" + corpus_preview},
        ]
    )

    personas = obj.get("personas") or []
    rows: List[Dict[str, Any]] = []
    for p in personas:
        persona = (p.get("persona") or "").strip()
        for t in p.get("tasks") or []:
            task = (t.get("task") or "").strip()
            for q in t.get("questions") or []:
                question = str(q).strip()
                if not question:
                    continue
                rows.append({"persona": persona, "task": task, "question": question})

    # Ensure <= 125, best effort
    rows = rows[:125]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM evaluation_questions WHERE job_id = ?", (job_id,))
        for r in rows:
            await db.execute(
                "INSERT INTO evaluation_questions (job_id, persona, task, question) VALUES (?, ?, ?, ?)",
                (job_id, r["persona"], r["task"], r["question"]),
            )
        await db.commit()

    return len(rows)

