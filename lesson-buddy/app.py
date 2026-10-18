"""Lesson Buddy: a RAG assistant for teachers.

Run with:  streamlit run app.py
"""

import html
import json
import re
import shutil
import time
from pathlib import Path

import streamlit as st

from rag.generate import answer, exit_ticket, focus_plan, plan_to_markdown
from rag.ingest import chunk_text, load_file, read_text
from rag.store import LessonStore

SAMPLES = Path(__file__).parent / "data" / "sample_lessons"
FEEDBACK_LOG = Path("feedback.jsonl")
LIBRARY = Path(".library")  # full text of each file, for the View tab
STEP_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756", "#72B7B2"]

st.set_page_config(page_title="Lesson Buddy", page_icon="🍎", layout="wide")


@st.cache_resource
def get_store() -> LessonStore:
    return LessonStore()


store = get_store()


def preview(text: str, limit: int = 500) -> str:
    """Show a source passage as plain text: drop Markdown headings and bold so
    a section title like '## Assessment' isn't rendered huge and clipped."""
    clean = re.sub(r"^#+\s*", "", text, flags=re.M).replace("**", "")
    clean = " ".join(clean.split())  # collapse line breaks into one paragraph
    return clean[:limit] + ("…" if len(clean) > limit else "")


def save_original(name: str, text: str) -> None:
    LIBRARY.mkdir(exist_ok=True)
    (LIBRARY / f"{name}.txt").write_text(text)


def load_original(name: str) -> str:
    for path in (LIBRARY / f"{name}.txt", SAMPLES / name):
        if path.exists():
            return path.read_text()
    return store.all_text(name)  # fallback: stitch the indexed chunks back together


def render_plan(plan: dict | str) -> None:
    """Draw a focused lesson plan: summary card, timeline bar, one card per step."""
    if isinstance(plan, str):  # model reply couldn't be structured; show it as text
        with st.container(border=True):
            st.markdown(plan)
        return

    steps = plan["steps"]
    total = sum(s["minutes"] for s in steps)

    with st.container(border=True):
        st.markdown(f"### 🎯 {plan.get('focus', 'Focused mini-lesson')}")
        meta = " · ".join(x for x in [plan.get("grade_subject"), f"{total} minutes"] if x)
        st.caption(meta)
        st.markdown(f"**Objective:** {plan.get('objective', '')}")
        if plan["materials"]:
            st.markdown("**Materials:** " + " · ".join(plan["materials"]))

    # Timeline: each block's width is proportional to its minutes.
    blocks = "".join(
        f'<div title="{html.escape(s["name"])}: {s["minutes"]} min" '
        f'style="flex:{s["minutes"]};background:{STEP_COLORS[i % len(STEP_COLORS)]};'
        f'color:white;padding:10px 8px;font-size:0.85rem;white-space:nowrap;'
        f'overflow:hidden;text-overflow:ellipsis;">'
        f'<b>{html.escape(s["name"])}</b><br>{s["minutes"]} min</div>'
        for i, s in enumerate(steps)
    )
    st.markdown(
        f'<div style="display:flex;gap:3px;border-radius:10px;overflow:hidden;margin:4px 0 14px;">'
        f"{blocks}</div>",
        unsafe_allow_html=True,
    )

    for i, s in enumerate(steps):
        color = STEP_COLORS[i % len(STEP_COLORS)]
        with st.container(border=True):
            st.markdown(
                f'<span style="color:{color};font-size:1.2rem;">●</span> '
                f'<b>{html.escape(s["name"])}</b> · ⏱ {s["minutes"]} min',
                unsafe_allow_html=True,
            )
            st.markdown("\n".join(f"- {a}" for a in s["activities"]) or "_No details given._")

    d = plan["differentiation"]
    labels = [("support", "🤝 Support"), ("extension", "🚀 Extension"), ("ell", "🌎 English learners")]
    shown = [(label, d[k]) for k, label in labels if d.get(k)]
    if shown:
        st.markdown("**Differentiation**")
        for col, (label, text) in zip(st.columns(len(shown)), shown):
            with col.container(border=True):
                st.markdown(f"**{label}**")
                st.write(text)


def log_feedback(kind: str, query: str, output: str, rating: str) -> None:
    """Every thumbs up/down is saved so we can see what's working and improve prompts."""
    with FEEDBACK_LOG.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "kind": kind, "query": query,
                            "rating": rating, "output": output}) + "\n")
    st.toast("Thanks, feedback saved!")


# ---------- Sidebar: the teacher's library ----------
with st.sidebar:
    st.header("📚 Your materials")
    uploads = st.file_uploader("Upload lesson plans", type=["pdf", "md", "txt"],
                               accept_multiple_files=True)
    if uploads and st.button("Add to library", type="primary"):
        n = 0
        for u in uploads:
            text = read_text(u.name, u.getvalue())
            save_original(u.name, text)
            n += store.add(chunk_text(text, u.name))
        st.success(f"Indexed {n} chunks from {len(uploads)} file(s).")

    if st.button("Load sample lessons"):
        n = sum(store.add(load_file(p)) for p in sorted(SAMPLES.glob("*.md")))  # originals read from data/
        st.success(f"Indexed {n} chunks from the samples.")

    sources = store.sources()
    st.caption(f"{len(sources)} file(s), {store.count()} chunks indexed")
    for s in sources:
        st.markdown(f"- {s}")
    if sources and st.button("Clear library"):
        store.reset()
        shutil.rmtree(LIBRARY, ignore_errors=True)
        st.rerun()

# ---------- Main area ----------
st.title("🍎 Lesson Buddy")
st.write("Ask questions about your lesson materials, plan a focused reteach, or turn a lesson into an exit ticket.")

ask_tab, ticket_tab, view_tab = st.tabs(
    ["💬 Ask your materials", "📝 Make an exit ticket", "📖 View lessons"]
)

with ask_tab:
    scope = st.selectbox("Search in", ["All materials"] + sources)
    q = st.text_input("Your question",
                      placeholder="Which standards does the fractions lesson cover?")
    if st.button("Ask", type="primary") and q:
        passages = store.search(q, k=4, source=None if scope == "All materials" else scope)
        with st.spinner("Reading your materials..."):
            try:
                st.session_state.last = (q, answer(q, passages), passages)
                st.session_state.pop("plan", None)  # new question, new plan
            except Exception as e:  # missing key, network, etc.
                st.error(str(e))

    if "last" in st.session_state:
        q_, a_, passages_ = st.session_state.last
        st.markdown(a_)
        with st.expander("Sources used"):
            for i, p in enumerate(passages_, start=1):
                st.markdown(f"**[{i}] {p['source']}** · similarity {p['score']}")
                st.caption(preview(p["text"]))
        c1, c2, _ = st.columns([1, 1, 8])
        if c1.button("👍", key="up"):
            log_feedback("answer", q_, a_, "up")
        if c2.button("👎", key="down"):
            log_feedback("answer", q_, a_, "down")

        # ----- Turn the answer into a focused mini-lesson -----
        st.divider()
        st.markdown("**Want to act on this?** Turn it into a short lesson that targets it.")
        if st.button("✨ Generate a focused lesson plan", type="primary") and passages_:
            with st.spinner("Planning a focused mini-lesson..."):
                try:
                    st.session_state.plan = focus_plan(q_, a_, passages_)
                except Exception as e:
                    st.error(str(e))

        if "plan" in st.session_state:
            plan = st.session_state.plan
            plan_md = plan_to_markdown(plan)
            render_plan(plan)
            st.caption("Items marked (suggested) are new ideas, not from your materials. "
                       "Numbers like [1] point to the sources above.")
            st.download_button("Download lesson plan", plan_md, file_name="focused_lesson_plan.md")
            p1, p2, _ = st.columns([1, 1, 8])
            if p1.button("👍", key="p_up"):
                log_feedback("focus_plan", q_, plan_md, "up")
            if p2.button("👎", key="p_down"):
                log_feedback("focus_plan", q_, plan_md, "down")

with ticket_tab:
    if not sources:
        st.info("Add some materials in the sidebar first.")
    else:
        lesson = st.selectbox("Lesson", sources, key="ticket_src")
        n = st.slider("Number of questions", 3, 8, 5)
        if st.button("Generate exit ticket", type="primary"):
            with st.spinner("Writing questions..."):
                try:
                    st.session_state.ticket = (lesson, exit_ticket(store.all_text(lesson), n))
                except Exception as e:
                    st.error(str(e))
        if "ticket" in st.session_state:
            src, ticket = st.session_state.ticket
            st.markdown(ticket)
            st.download_button("Download as Markdown", ticket,
                               file_name=f"exit_ticket_{Path(src).stem}.md")
            c1, c2, _ = st.columns([1, 1, 8])
            if c1.button("👍", key="t_up"):
                log_feedback("exit_ticket", src, ticket, "up")
            if c2.button("👎", key="t_down"):
                log_feedback("exit_ticket", src, ticket, "down")

with view_tab:
    if not sources:
        st.info("Add some materials in the sidebar first.")
    else:
        chosen = st.selectbox("Lesson", sources, key="view_src")
        with st.container(border=True):
            st.markdown(load_original(chosen))
