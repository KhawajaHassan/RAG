from typing import Any, Dict, List

from chromadb import Client
from chromadb.config import Settings as ChromaSettings

from ..config import settings
from ..llm import chat, embed


def get_chroma_client(persist_directory: str) -> Client:
  return Client(
      ChromaSettings(
          is_persistent=True,
          persist_directory=persist_directory,
      )
  )


async def run_vector_rag(
    *,
    job_id: str,
    question: str,
) -> Dict[str, Any]:
  chroma = get_chroma_client(str(settings.chroma_dir))
  collection = chroma.get_or_create_collection(name=f"job_{job_id}")

  # Embed query using Ollama
  query_vec: List[float] = embed(question)

  # Retrieve top-k
  top_k = settings.default_top_k
  results = collection.query(query_embeddings=[query_vec], n_results=top_k)

  documents: List[str] = results.get("documents", [[]])[0]
  metadatas: List[Dict[str, Any]] = results.get("metadatas", [[]])[0]

  context = "\n\n".join(documents)

  messages = [
      {
          "role": "system",
          "content": "You are a helpful assistant performing retrieval-augmented question answering over academic / technical documents.",
      },
      {
          "role": "user",
          "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer in a clear, well-structured way and cite chunk indices when relevant.",
      },
  ]

  answer = chat(messages)

  return {
      "mode": "vector_rag",
      "answer": answer,
      "sources": metadatas,
  }

