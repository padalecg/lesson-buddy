# 🍎 Lesson Buddy

A retrieval-augmented generation (RAG) assistant for K-8 teachers. Upload lesson plans, ask questions about them in plain English, and get answers that cite the exact passage they came from. One click turns any lesson into a ready-to-print exit ticket.

> **Why:** Teachers spend hours hunting through binders and shared drives for "which lesson covered this standard?" or "what did we plan for ELL support?" Generic chatbots answer confidently but can't see the school's own materials, and they make things up. Lesson Buddy only answers from the teacher's materials, and shows its sources.

## Features

- **Ask your materials:** natural-language Q&A across all lessons or one specific file, with inline citations like [1] and an expandable view of every source passage used.
- **Focused lesson plan:** one click turns any answer (say, "students list reasons without support") into a 15-20 minute mini-lesson targeting it, built from the teacher's materials, with any new ideas labeled "(suggested)".
- **Exit ticket generator:** builds 3-8 grade-appropriate questions plus an answer key from a single lesson, downloadable as Markdown.
- **Honest "I don't know":** if the answer isn't in the uploaded materials, it says so instead of guessing.
- **Feedback loop:** 👍/👎 on every answer and exit ticket, logged to `feedback.jsonl` for prompt and retrieval tuning.
- **Retrieval evaluation:** a labeled question set and script that scores hit@1, hit@k and MRR, so changes to chunking or embeddings are measured, not guessed.

## How it works

```
 Upload (.pdf/.md/.txt)
        │
        ▼
 ┌──────────────┐   split into ~800-char overlapping chunks
 │  ingest.py   │
 └──────┬───────┘
        ▼
 ┌──────────────┐   embed each chunk (all-MiniLM-L6-v2) and store
 │  store.py    │   in Chroma, a local vector database
 └──────┬───────┘
        │   question ──► embed ──► top-4 most similar chunks
        ▼
 ┌──────────────┐   prompt Claude with ONLY those chunks,
 │ generate.py  │   require citations, refuse if not covered
 └──────┬───────┘
        ▼
   Streamlit UI (app.py) ──► 👍/👎 ──► feedback.jsonl
```

| File | What it does |
|---|---|
| `rag/ingest.py` | Reads PDF/Markdown/text and splits it into overlapping chunks |
| `rag/store.py` | Chroma wrapper: add (upsert), semantic search, filter by file |
| `rag/generate.py` | System prompts and Claude calls for answers and exit tickets |
| `app.py` | Streamlit web interface |
| `eval/run_eval.py` | Retrieval benchmark on `eval/questions.json` |
| `data/sample_lessons/` | Three sample lessons (Grade 3 math, Grade 4 ELA, Grade 5 science) |

## Run it locally

```bash
git clone https://github.com/<you>/lesson-buddy.git
cd lesson-buddy
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...                 # Windows: set ANTHROPIC_API_KEY=...
streamlit run app.py
```

Click **Load sample lessons** in the sidebar, then try:

- *Which standards does the fractions lesson cover?*
- *How do I help kids who think 1/8 is bigger than 1/4?*
- *Where does a tree's mass come from, according to the science lesson?*
- *What's the field trip schedule?* (not in the materials, so it should say so)

The first run downloads a small embedding model (~80 MB), which takes a minute.

## Evaluate retrieval

```bash
python -m eval.run_eval
```

Prints each question with the rank of the correct lesson, then a summary:

```
12 questions | hit@1 ... | hit@4 ... | MRR ...
```

No API key needed, since this tests only the retrieval step. Try changing `CHUNK_SIZE` in `rag/ingest.py` or `k` in the search and see how the scores move.

## Deploy (free)

1. Push to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), pick the repo and `app.py`.
3. Under **Secrets**, add `ANTHROPIC_API_KEY = "sk-ant-..."`.

## Roadmap

See [PRODUCT.md](PRODUCT.md) for the problem framing, success metrics and what I'd build next.
