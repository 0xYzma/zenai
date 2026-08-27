import chromadb
from app.core.config import get_settings
from functools import lru_cache


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def get_or_create_collection(workspace_id: str) -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=f"schema_{workspace_id}",
        metadata={"hnsw:space": "cosine"}
    )
