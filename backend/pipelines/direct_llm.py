from __future__ import annotations

from typing import Any, Dict

from ..llm import chat


async def run_direct_llm(*, question: str) -> Dict[str, Any]:
  answer = chat(
      [
          {"role": "system", "content": "You are a helpful assistant. If you don't know, say so."},
          {"role": "user", "content": question},
      ]
  )
  return {
      "mode": "direct_llm",
      "answer": answer,
      "sources": [],
  }

