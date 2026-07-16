# Qdrant × Future AGI — Agentic RAG Workshop

## What this is

A live, one-hour joint technical webinar run by Dylan (Qdrant) and Rishav (Future AGI).
The story: an agentic RAG system that used to work well has quietly gotten worse as it
grew. We build it, show where it's losing quality, fix the right layer, and prove each
fix worked. Qdrant powers retrieval and every fix. Future AGI traces and evaluates the
agent throughout.

This repo holds the demo agent, the ingestion/corpus scripts, the "break it on purpose"
setup, and the shared golden dataset. Future AGI's tracing and eval config layer on top.

## North Star

One continuous walkthrough where the audience *sees* quality move. Every change we make
should show up as a number changing on Future AGI's dashboard and, where possible, as
something visible in the Qdrant UI. No reading dicts off a terminal. If a viewer can't
tell whether a fix worked by looking at the screen, we haven't built it right.

The audience is AI and ML engineers running agentic RAG in production, or dealing with
retrieval quality that got harder to explain as the system grew. They should leave with
a repeatable workflow: find why the agent degraded, fix the right layer, verify the fix
improved the agent and not just an isolated metric.

## The arc (not locked, but this is the shape)

1. Show the agent. What it is, what it's supposed to do, a query that works.
2. Show it degrading. A quick look at quality dropping to set up the pain.
3. Measure (Future AGI). The dashboard lights up. Scores point to the real problem.
4. Fix the right layer (Qdrant). One issue at a time.
5. Measure again. Watch the metric move before moving on.
6. Repeat for each issue.
7. Compare before and after across all changes in Future AGI's Experiments view.

The handoff cue each time is Future AGI's diagnostic triad: `context_relevance`,
`chunk_utilization`, `groundedness`. Together they tell us whether a failure is a
retrieval problem (Dylan's to fix in Qdrant) or a generation problem.

## Division of labor

- **Qdrant / Dylan**: builds the agent, owns the retrieval layer and every fix
  (embedding migration, dedup, reranking, hybrid search, top-k), owns the Qdrant UI
  visuals.
- **Future AGI / Rishav**: owns instrumentation (traceAI, ~a few lines), eval
  definitions, reading the scores live, and the deeper eval-methodology segment.
- **Shared**: the golden dataset of test queries. It's the contract between the two
  halves and must be agreed jointly before anything else is built.

## What we're building (high level)

An **agentic** RAG system, not a single-shot retriever. The agent rewrites queries,
decides when to retrieve, may do multi-hop retrieval, and cites sources. This matters
because it opens up agentic failure modes (tool decisions, query rewriting, multi-hop)
on top of plain retrieval quality.

Framework is **not yet chosen** (LangChain, LlamaIndex, or direct Qdrant client). This
decision affects how retrieval gets traced: through LangChain/LlamaIndex, Qdrant calls
are auto-traced as retriever spans; direct client calls need a manual span. Default lean
is a framework with auto-instrumentation to keep the live demo simple. No build
instructions here until the framework is locked.

Corpus: something with obvious right and wrong answers so bad retrieval is visible on
stage. Use case is still open. We want something a bit flashy that demos well, not a
generic docs bot.

## Break it on purpose

The agent ships already broken, in specific ways that each map to one clean fix so the
scoreboard moves when we address it. Build the flaws in deliberately and, before the
session, confirm Future AGI's evals actually see each one. If a fix lands and no metric
moves, the narrative dies.

Candidate flaws to build in (pick 3–4 that each map to a clean fix):

- **Stale / weak embedding model.** Start on a small dated model. Fix: zero-downtime
  migration to a stronger model.
- **Duplicate and fragmented chunks.** Re-ingest overlapping copies, over-chunk with a
  tiny chunk size, no dedup. Best UI visual: dense clusters that thin out after dedup.
  Fix: dedup the collection.
- **No reranking.** Raw top-k vector search only. Fix: add late interaction (ColBERT-style)
  reranking.
- **Conflicting / outdated documents.** Old and new versions of the same doc both live in
  the collection, agent answers from the stale one. Strong "it grew and got worse" story.
- **Bad query rewriting.** The agent mangles the user's question before retrieval, so
  Qdrant gets a worse query than the user asked.
- **Lost in the middle.** Too many chunks stuffed into context, the relevant one ignored.
  Argues for reranking and tighter top-k.

## Potential failure modes and what detects them

| Failure mode | Layer | Future AGI signal |
|---|---|---|
| Weak/stale embeddings retrieve poor chunks | retrieval | `context_relevance` low |
| Duplicate / fragmented chunks | retrieval | `context_relevance`, `chunk_utilization` low |
| No reranking, relevant chunk ranked low | retrieval | `chunk_utilization`, lost-in-the-middle |
| Conflicting / outdated docs | data/retrieval | `groundedness` fail, source attribution |
| Bad query rewriting | agent | `context_relevance` drops despite a good index |
| Wrong retrieval decision (retrieves when it shouldn't, or skips) | agent | tool-call spans |
| Multi-hop breakdown | agent | session / trace view |
| Hallucinated citations | generation | `chunk_attribution` fail |
| Answer ignores good context | generation | `chunk_utilization`, `completeness` |
| Hallucination / unsupported claims | generation | `faithfulness`, `groundedness` |
| Latency / cost creep | system | per-step tokens and latency in tracing |

Rule of thumb from Future AGI's own docs: low `context_relevance` + low
`chunk_utilization` means the retriever is fetching irrelevant chunks, so the fix is in
Qdrant (embeddings, reranking, top-k). Good `context_relevance` but low
`chunk_utilization` or failing `groundedness` points at the generation side.

## Expected outcomes

- Every fix produces a visible, verifiable score improvement.
- A clear before/after comparison across all changes at the end.
- A repeatable diagnostic workflow the audience can take home: measure → locate the
  failing layer → fix it → verify against the same eval set.
- A clean two-product handoff that never has one presenter building the other's part.

## Visual bar

- Qdrant Web UI: show chunks as points, duplicates as tight clusters, dedup thinning
  them out, retrieval hits highlighted per query.
- Future AGI dashboard on screen alongside so scores move the moment a fix lands.
- Notebook with rich inline output (score cards / bar charts), not printed dicts.
- A persistent scoreboard: a handful of metrics with before/after and a running delta.

## Reference

Full research on how Future AGI's product works (products, evals, tracing, experiments,
setup) lives with Dylan. Key packages: `ai-evaluation` (evals, `from fi.evals import
evaluate`), `fi-instrumentation-otel` + `traceAI-<framework>` (tracing), `futureagi`
(platform SDK incl. datasets/experiments). Auth via `FI_API_KEY` + `FI_SECRET_KEY`.
