"""Turn lesson files into small, overlapping text chunks.

Why chunk at all? An LLM can only read so much at once, and a vector
search works best on short passages that are about one idea. We split each
document on paragraph breaks, then pack paragraphs into chunks of roughly
CHUNK_SIZE characters, carrying a little overlap forward so an idea that
straddles a boundary isn't lost.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

CHUNK_SIZE = 800  # characters, roughly 150-200 words
OVERLAP = 150     # characters carried into the next chunk


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    index: int


def read_text(name: str, data: bytes) -> str:
    """Extract plain text from a .txt, .md or .pdf file's bytes."""
    if name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="ignore")


def chunk_text(text: str, source: str) -> list[Chunk]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            i = len(chunks)
            chunks.append(Chunk(id=f"{source}::{i}", text=current.strip(), source=source, index=i))
            current = current[-OVERLAP:]  # keep a tail for context

    for para in paragraphs:
        # A single huge paragraph gets hard-split so no chunk runs away.
        while len(para) > CHUNK_SIZE:
            current += "\n\n" + para[:CHUNK_SIZE]
            para = para[CHUNK_SIZE:]
            flush()
        if len(current) + len(para) > CHUNK_SIZE:
            flush()
        current += "\n\n" + para
    flush()
    return chunks


def load_file(path: Path) -> list[Chunk]:
    return chunk_text(read_text(path.name, path.read_bytes()), source=path.name)
