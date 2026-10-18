"""Prompts and LLM calls.

This is the "G" in RAG: we hand the model the retrieved passages and ask it
to answer ONLY from them, citing which passage each claim came from. That
grounding is what keeps a teacher-facing tool from making things up.
"""

from __future__ import annotations

import json
import os

import anthropic

MODEL = os.getenv("LESSON_BUDDY_MODEL", "claude-sonnet-5-5")

ANSWER_SYSTEM = """You are Lesson Buddy, an assistant for K-8 teachers.
Answer the teacher's question using ONLY the numbered passages provided.
- Cite passages inline like [1] or [2][3].
- If the passages don't contain the answer, say so plainly and suggest what
  material the teacher could upload. Never invent standards, page numbers or facts.
- Be concise and practical: teachers are busy. Prefer short paragraphs or bullets."""

EXIT_TICKET_SYSTEM = """You write exit tickets: quick end-of-class checks for understanding.
Use ONLY the lesson text provided. Write in Markdown:
1. A one-line title naming the lesson objective.
2. Exactly {n} questions for grade-level students: mix multiple choice (4 options)
   and one short-answer question. Keep wording simple and unambiguous.
3. An "Answer key" section, with one sentence per question on what a correct
   answer shows the student understands.
Do not use content that isn't in the lesson."""

FOCUS_PLAN_SYSTEM = """You write short, focused mini-lesson plans for K-8 teachers.
The teacher asked a question about their lesson materials and got an answer.
Write a 15-20 minute mini-lesson that targets the specific skill, struggle or
topic in that answer. Build on the teacher's own materials (the numbered
passages) wherever possible and cite them inline like [1].

Reply with ONLY a JSON object (no Markdown fences, no extra text) in this shape:
{
  "focus": "one line naming the skill or struggle",
  "objective": "Students will be able to ...",
  "grade_subject": "e.g. Grade 4 ELA",
  "materials": ["short item", "..."],
  "steps": [
    {"name": "Warm-up", "minutes": 3, "activities": ["concrete step", "..."]},
    {"name": "Teach", "minutes": 5, "activities": ["..."]},
    {"name": "Practice", "minutes": 7, "activities": ["..."]},
    {"name": "Quick check", "minutes": 3, "activities": ["..."]}
  ],
  "differentiation": {"support": "...", "extension": "...", "ell": "..."}
}

Rules:
- Keep the same grade level and subject as the passages.
- Minutes must be whole numbers and add up to 15-20.
- 2-4 short, concrete activities per step; each one is a single sentence.
- Anything NOT from the passages (a new activity, example or question) must end
  with "(suggested)" so the teacher knows it is new.
- Never invent standards codes. No filler."""


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("Set ANTHROPIC_API_KEY (see README) to generate answers.")
    return anthropic.Anthropic()


def format_context(passages: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] (from {p['source']})\n{p['text']}" for i, p in enumerate(passages, start=1)
    )


def _text(msg) -> str:
    """Return only the answer text. Newer models may include 'thinking'
    blocks before the answer, so we keep just the text blocks."""
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def answer(question: str, passages: list[dict]) -> str:
    if not passages:
        return "I don't have any lesson materials yet. Upload a file or load the samples first."
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=2000,
        system=ANSWER_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Passages:\n\n{format_context(passages)}\n\nTeacher's question: {question}",
        }],
    )
    return _text(msg)


def exit_ticket(lesson_text: str, n: int = 5) -> str:
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=3000,
        system=EXIT_TICKET_SYSTEM.format(n=n),
        messages=[{"role": "user", "content": f"Lesson:\n\n{lesson_text}"}],
    )
    return _text(msg)


def focus_plan(question: str, answer_text: str, passages: list[dict]) -> dict | str:
    """Turn an answer into a short, targeted mini-lesson grounded in the same passages.

    Returns a dict (structured plan, so the app can draw it visually), or the raw
    text if the model's reply couldn't be parsed, so the teacher still gets a plan.
    """
    msg = _client().messages.create(
        model=MODEL,
        max_tokens=4000,
        system=FOCUS_PLAN_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Passages:\n\n{format_context(passages)}\n\n"
                f"Teacher's question: {question}\n\n"
                f"Answer they received:\n{answer_text}\n\n"
                "Write the focused mini-lesson plan as JSON."
            ),
        }],
    )
    raw = _text(msg)
    return parse_plan(raw) or raw


def parse_plan(raw: str) -> dict | None:
    """Pull the JSON object out of the reply and check it has what the UI needs."""
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    for st in steps:
        try:
            st["minutes"] = max(1, int(st.get("minutes", 1)))
        except (TypeError, ValueError):
            st["minutes"] = 1
        st["activities"] = [str(a) for a in st.get("activities", []) if a]
        st["name"] = str(st.get("name", "Step"))
    data.setdefault("materials", [])
    data.setdefault("differentiation", {})
    return data


def plan_to_markdown(plan: dict | str) -> str:
    """Printable/downloadable version of a plan."""
    if isinstance(plan, str):
        return plan
    total = sum(s["minutes"] for s in plan["steps"])
    lines = [f"# Focus: {plan.get('focus', '')}", ""]
    if plan.get("grade_subject"):
        lines.append(f"**{plan['grade_subject']}** · {total} minutes")
    lines += ["", f"**Objective:** {plan.get('objective', '')}", ""]
    if plan["materials"]:
        lines += ["**Materials:**"] + [f"- {m}" for m in plan["materials"]] + [""]
    for s in plan["steps"]:
        lines += [f"## {s['name']} ({s['minutes']} min)"] + [f"- {a}" for a in s["activities"]] + [""]
    d = plan["differentiation"]
    if d:
        lines += ["## Differentiation"]
        for key, label in (("support", "Support"), ("extension", "Extension"), ("ell", "English language learners")):
            if d.get(key):
                lines.append(f"- **{label}:** {d[key]}")
    return "\n".join(lines).strip() + "\n"
