# Qdrant × Future AGI: Agentic RAG Workshop

A live demo of an agentic RAG system that decayed as its corpus grew. The audience watches answer quality slide, finds the failing retrieval layer on Future AGI's dashboard, fixes that layer in Qdrant, and sees the score recover. Corpus: all 1,025 Pokémon from [PokéAPI](https://pokeapi.co), with realistic re-crawl duplication baked in.

- **How the hour runs** (beats, timings, expected numbers, fallbacks): `RUNBOOK.md`
- **Design rationale and verified measurements**: `CLAUDE.md`

## Setup

```bash
uv sync
cp .env.example .env          # fill in the five keys
```

`.env` needs `QDRANT_URL`, `QDRANT_API_KEY` (Qdrant Cloud, v1.18+), `ANTHROPIC_API_KEY`, `FI_API_KEY`, `FI_SECRET_KEY` (Future AGI).

## 1 · Build the Collections

Already done on the shared cluster, so you can skip to Start. On a fresh cluster:

```bash
uv run python ingest.py       # broken-on-purpose baseline + pokemon_viz
uv run python prep.py         # backfill the fix vectors, then snapshot both collections
```

`prep.py` ends by snapshotting the finished state on the cluster, so every later destructive step is revertible. The backfill is resumable: if the encoder process dies partway, rerun `prep.py` and it continues where it stopped.

## 2 · Start

```bash
uv run streamlit run app.py               # Pokédex chat UI + retrieval panel
uv run jupyter lab workshop.ipynb         # the fixes, one section each
```

Ask the app any Pokémon question. The notebook performs the fixes against the live collection; the app picks up each fix on the next question.

## 3 · Restore

After anything destructive (the notebook's dedup, `verify_arc.py`, a rehearsal), revert both collections to the show-ready baseline in seconds:

```bash
uv run python snapshot.py restore
```

`restore` prefers the [snapshot](https://qdrant.tech/documentation/snapshots/) stored on the cluster and falls back to the newest local `data/{collection}-*.snapshot` file. `snapshot.py download` saves the cluster snapshots to `data/`; `snapshot.py backup` re-snapshots the current state. Snapshot files are gitignored (the main one is 462 MB).

After a restore, check `data/.retrieval_state.json` reads `{"mode": "minilm", "current_only": false}`. The full pre-show checklist is in `RUNBOOK.md`.

## Where Future AGI Plugs In

**Tracing is already wired.** `agent.py` registers Future AGI tracing at import:

```python
trace_provider = register(project_type=ProjectType.OBSERVE, project_name="pokedex-rag")
LangChainInstrumentor().instrument(tracer_provider=trace_provider)
```

With `FI_API_KEY` set, every process that runs the agent (the Streamlit app, the notebook, the rehearsal scripts) exports traces to the **`pokedex-rag`** project, with Qdrant retrieval as retriever spans. There is no separate tracing setup step.

**The golden set is the shared eval dataset.** `data/golden_dataset.jsonl`, 37 queries, one JSON object per line:

| Field | Meaning |
|---|---|
| `query` | the question the agent gets |
| `expected_answer` | known-good answer (the cold-open custom judge scores against this) |
| `gold_doc_ids` | doc-level gold labels for IR metrics. Stable across re-ingest and re-embed; never point ids |
| `exercises` | which beat the query exercises: `cold_open`, `fix1_dedup`, `fix2_embedding`, `fix3_hybrid`, `multi_hop` |
| `notes` | selection evidence (measured ranks that qualified the query) |

**Evals per beat** (the notebook prints local gold-label checks; judged scores live on your dashboard, never in our UI):

| Beat | Platform eval |
|---|---|
| Cold open | custom LLM judge vs `expected_answer` (a stale-but-cited answer passes groundedness, so groundedness can't score this) |
| Fix #1 dedup | `chunk_utilization` + the retrieval panel visual |
| Fix #2 migration | `Recall@K` + `context_relevance` |
| Fix #3 hybrid + rerank | `NDCG@K`, `MRR`, `Recall@K` |
| Every handoff | the triad read: `context_relevance` + `chunk_utilization` + `groundedness` → retrieval problem or generation problem |

**Measured SDK behavior to anchor dashboard reads** (via `ai-evaluation`, `model="turing_flash"`, context passed as one string): `groundedness` stays green through retrieval failures because a grounded "I don't know" passes; `context_relevance` dips on a dense miss but never collapses; `chunk_utilization` scores the answer's use of context, not duplication.

**Open items for the Future AGI team:**

1. How platform dataset runs present the triad vs standalone SDK calls, and which anchors each beat's dashboard read.
2. Gold-label format for IR metrics on the platform (our canonical format is the JSONL described in the preceding table; we'll write a converter to whatever the platform expects).
3. The Experiments view setup for the before/after scoreboard (RUNBOOK beat at 0:51).

## The Fixes

The agent's retrieval mode is a file-backed switch (`agent.set_retrieval`). The notebook flips it; the app reads it on each question and shows the active mode as a badge.

1. **Dedup**: delete duplicate points. Duplicate rate in the top-5 drops 0.67 → 0.00; the collection shrinks 22.9k → 8.4k points.
2. **Embedding migration**: add `bge-large` as a named vector on the live collection (zero downtime), A/B both models on the golden set, and commit: the 384d model stopped separating the clone Pokémon once the dex grew to 1,025 species (recall 0.64 → 1.00). The same one-line flip rolls back if the number goes the other way.
3. **Hybrid + rerank**: one multi-stage `query_points` call: dense (bge) + sparse (miniCOIL) prefetch, RRF fusion, ColBERT rerank. Takes the hard paraphrase set from recall 0.83 to 1.00 on top of the migrated model.
4. **Cold-open close**: an `is_current` payload filter removes the stale type-chart document that dedup, the bigger model, and hybrid all failed to beat.

Models (all local via FastEmbed): `all-MiniLM-L6-v2` (384d), `BAAI/bge-large-en-v1.5` (1024d), `Qdrant/minicoil-v1` sparse, `colbert-ir/colbertv2.0` rerank.

## Layout

| Path | Role | On camera |
|---|---|---|
| `app.py` | Pokédex chat UI + retrieval panel | runs on screen |
| `agent.py` | LangGraph agent: Qdrant retrieval, tracing, grounding | shown |
| `workshop.ipynb` | the fixes, one section each | shown |
| `ingest.py` / `prep.py` | broken ingestion / offline vector backfill + snapshot | never |
| `snapshot.py` | backup/restore/download the show state | never |
| `scaling_curve.py` | regenerates the decay-curve chart | never |
| `verify_arc.py` | rehearsal gate: flaws red, fixes move (`--baseline-only` is non-destructive) | never |
| `helpers/` | PokéAPI, chunking, embeddings, UI | never |
| `data/golden_dataset.jsonl` | queries, expected answers, gold `doc_id`s | n/a |

## Notes

- `traceAI-langchain` requires `langchain<0.4`, so the agent uses `langgraph.prebuilt.create_react_agent`; switch to `langchain.agents.create_agent` when Future AGI supports langchain 1.x.
- Nintendo IP: fine for a live demo, don't publish the corpus as a downloadable artifact.
