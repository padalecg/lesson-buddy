"""A thin wrapper around Chroma, the vector database.

Chroma turns each chunk into an embedding (a list of numbers that captures
its meaning) using a small local model, so "kids splitting a pizza" and
"equal parts of a whole" end up close together even with no shared words.
At question time we embed the question and return the nearest chunks.
"""

from __future__ import annotations

import chromadb

from .ingest import Chunk

DB_PATH = ".chroma"
COLLECTION = "lessons"


class LessonStore:
    def __init__(self, path: str = DB_PATH, embedding_function=None):
        # None = Chroma's default local model (all-MiniLM-L6-v2, downloaded on first run)
        self.client = chromadb.PersistentClient(path=path)
        self._ef = embedding_function
        self.col = self._collection()

    def _collection(self):
        kwargs = {"embedding_function": self._ef} if self._ef else {}
        return self.client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"}, **kwargs
        )

    def add(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        # upsert: re-uploading the same file replaces it instead of duplicating
        self.col.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, "index": c.index} for c in chunks],
        )
        return len(chunks)

    def search(self, query: str, k: int = 4, source: str | None = None) -> list[dict]:
        if self.count() == 0:
            return []
        where = {"source": source} if source else None
        res = self.col.query(query_texts=[query], n_results=min(k, self.count()), where=where)
        return [
            {"text": doc, "source": meta["source"], "score": round(1 - dist, 3)}
            for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]

    def sources(self) -> list[str]:
        metas = self.col.get(include=["metadatas"])["metadatas"]
        return sorted({m["source"] for m in metas})

    def all_text(self, source: str) -> str:
        got = self.col.get(where={"source": source}, include=["documents", "metadatas"])
        pairs = sorted(zip(got["metadatas"], got["documents"]), key=lambda p: p[0]["index"])
        return "\n\n".join(doc for _, doc in pairs)

    def count(self) -> int:
        return self.col.count()

    def reset(self) -> None:
        self.client.delete_collection(COLLECTION)
        self.col = self._collection()
