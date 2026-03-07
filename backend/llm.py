from __future__ import annotations

import json
from typing import Any, Dict, List

import ollama

from .config import settings


def chat(messages: List[Dict[str, str]]) -> str:
  """
  Thin wrapper around ollama.chat that returns the assistant message content.
  """
  resp = ollama.chat(model=settings.ollama_chat_model, messages=messages)
  # Ollama returns a single message in resp["message"]
  return (resp.get("message") or {}).get("content") or ""


def chat_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
  """
  Call Ollama and best-effort parse a JSON object from the response.
  Prompts using this MUST instruct the model to return ONLY JSON.
  """
  text = chat(messages)
  try:
    return json.loads(text)
  except Exception:
    # Try to recover a JSON substring if the model wrapped it in prose
    try:
      start = text.index("{")
      end = text.rindex("}") + 1
      return json.loads(text[start:end])
    except Exception:
      return {}


def embed(text: str) -> List[float]:
  """
  Single-text embedding via Ollama.
  """
  resp = ollama.embeddings(model=settings.ollama_embedding_model, prompt=text)
  return resp.get("embedding") or []


def embed_many(texts: List[str]) -> List[List[float]]:
  return [embed(t) for t in texts]

