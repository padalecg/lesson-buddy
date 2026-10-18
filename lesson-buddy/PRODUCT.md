# Lesson Buddy: Product One-Pager

## Problem

Teachers in a school network reuse and adapt a large library of lesson plans, but finding the right detail is slow: which lesson hits a given standard, what the planned differentiation was, which misconceptions to watch for. Generic AI chat tools can't see the network's own curriculum and will invent plausible but wrong answers, which erodes trust fast.

## Users

- **Primary:** classroom teachers prepping tomorrow's lesson (time-poor, often prepping in the evening).
- **Secondary:** instructional coaches and curriculum leads checking coverage across grades.

## Hypothesis

If teachers can ask their own materials questions and get grounded, cited answers in seconds, they will spend less time on lesson prep and use more of the network's existing curriculum (instead of improvising or searching the open web).

## What v1 does

1. Grounded Q&A over uploaded lesson materials, with citations.
2. Exit ticket generation from a single lesson.
3. Thumbs up/down on every output.

Deliberately out of scope for v1: student-facing features, grading, writing to any school system, and student data of any kind.

## Success metrics

| Type | Metric | Why |
|---|---|---|
| North star | Prep minutes saved per teacher per week (self-reported + task timing) | Ties to the efficiency goal |
| Quality | Retrieval hit@4 on the eval set ≥ 90% | If retrieval misses, nothing downstream can be right |
| Quality | 👍 rate on answers ≥ 80%; hallucination rate (audited sample) < 2% | Trust is the product |
| Adoption | Weekly active teachers; % of exit tickets used in class without edits | Shows real workflow fit, not novelty |
| Guardrail | "Not in your materials" responses that were actually answerable | Catches over-cautious refusals |

## Risks and mitigations

- **Hallucination:** answer only from retrieved passages, show sources, eval set + audited samples before each prompt change.
- **Privacy:** v1 ingests curriculum only, never student data. Before any expansion, review FERPA obligations and vendor data retention.
- **Stale or conflicting materials:** show file names and versions in citations; let curriculum leads mark the canonical version.
- **Over-reliance:** position as a prep aid; teachers review all generated assessments.

## Next experiments

1. **Hybrid search** (keyword + semantic) to fix exact-term misses like standard codes; measure hit@1 lift on the eval set.
2. **Standards tagging** at ingest so teachers can filter by "3.NF.A.1" and coaches can see coverage gaps across a grade.
3. **Feedback → eval set:** turn every 👎 into a new labeled eval question so the benchmark grows from real usage.
4. **Google Drive connector** so materials stay in sync without manual uploads.
