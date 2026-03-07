from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Multi-Document Reasoning with Graph-Augmented RAG"
    database_path: Path = Path(__file__).resolve().parent / "app.db"
    chroma_dir: Path = Path(__file__).resolve().parent / "chroma"

    # Ollama models
    ollama_chat_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"

    # Chunking
    chunk_size: int = 600
    chunk_overlap: int = 100

    # Graph / search
    max_context_tokens: int = 8000
    default_top_k: int = 8
    ego_k_hops: int = 2


settings = Settings()

