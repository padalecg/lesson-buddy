"""Measure retrieval quality on a small labeled question set.

For each question we know which lesson holds the answer. We check:
  - hit@1: was the top result from the right lesson?
  - hit@k: was the right lesson anywhere in the top k?
  - MRR:   mean reciprocal rank (1.0 = always first, 0.5 = usually second)

This needs no API key: it only tests the "R" in RAG. If retrieval misses,
the model can't answer well no matter how good the prompt is, so this is the
first number to watch when you change chunk size, embeddings or k.

Run from the project root:  python -m eval.run_eval
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.ingest import load_file  # noqa: E402
from rag.store import LessonStore  # noqa: E402

K = 4


def main() -> None:
    questions = json.loads((ROOT / "eval" / "questions.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        store = LessonStore(path=tmp)  # fresh, throwaway index
        for p in sorted((ROOT / "data" / "sample_lessons").glob("*.md")):
            store.add(load_file(p))

        hit1 = hitk = rr = 0.0
        for item in questions:
            ranked = [r["source"] for r in store.search(item["q"], k=K)]
            rank = ranked.index(item["expected"]) + 1 if item["expected"] in ranked else None
            hit1 += rank == 1
            hitk += rank is not None
            rr += 1 / rank if rank else 0
            mark = "✓" if rank == 1 else ("~" if rank else "✗")
            print(f"{mark} rank={rank or '-'}  {item['q']}")

    n = len(questions)
    print(f"\n{n} questions | hit@1 {hit1 / n:.0%} | hit@{K} {hitk / n:.0%} | MRR {rr / n:.2f}")


if __name__ == "__main__":
    main()
