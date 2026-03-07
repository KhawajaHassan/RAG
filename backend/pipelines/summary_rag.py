from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from ..config import settings
from ..llm import chat, chat_json


def _batch_text(chunks: List[str], approx_chars: int = 9000) -> List[str]:
  batches: List[str] = []
  buf: List[str] = []
  size = 0
  for ch in chunks:
    size += len(ch)
    buf.append(ch)
    if size >= approx_chars:
      batches.append("\n\n".join(buf))
      buf = []
      size = 0
  if buf:
    batches.append("\n\n".join(buf))
  return batches


async def run_summary_rag(
    *,
    question: str,
    raw_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
  texts = [c["content"] for c in raw_chunks]
  batches = _batch_text(texts)

  map_outputs: List[Tuple[int, str, int]] = []
  for i, b in enumerate(batches):
    prompt = (
        "You will answer a question using ONLY the provided text batch.\n"
        "Return ONLY a JSON object with keys: partial_answer (string), helpfulness_score (0-100).\n"
        "If the batch is irrelevant, set helpfulness_score to 0 and partial_answer to \"\".\n\n"
        f"Question: {question}\n\nBatch:\n{b}"
    )
    try:
      obj = chat_json(
          [
              {"role": "system", "content": "You are a careful research assistant. Respond with JSON only."},
              {"role": "user", "content": prompt},
          ]
      )
      ans = (obj.get("partial_answer") or "").strip()
      score = int(obj.get("helpfulness_score") or 0)
    except Exception:
      ans = ""
      score = 0

    map_outputs.append((i, ans, max(0, min(100, score))))

  kept = [(i, ans, score) for (i, ans, score) in map_outputs if score > 0 and ans]
  kept.sort(key=lambda t: t[2], reverse=True)

  # Reduce: concatenate by score into a final context window
  reduced_parts: List[str] = []
  char_budget = settings.max_context_tokens * 4  # very rough
  used = 0
  for _, ans, score in kept:
    piece = f"[score={score}]\n{ans}"
    if used + len(piece) > char_budget:
      break
    reduced_parts.append(piece)
    used += len(piece)

  reduce_context = "\n\n".join(reduced_parts)

  final_prompt = (
      "You are given scored partial answers from a map stage.\n"
      "Synthesize a single final answer. If there is insufficient information, say so and ask a targeted follow-up.\n\n"
      f"Question: {question}\n\nScored partial answers:\n{reduce_context}"
  )
  answer = chat(
      [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": final_prompt},
      ]
  )

  return {
      "mode": "summary_rag",
      "answer": answer,
      "sources": [{"batch_index": i, "score": s} for (i, _, s) in kept],
  }

