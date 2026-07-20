# Qdrant × Future AGI: Agentic RAG Workshop

A live demo of an agentic RAG system that worked on a small corpus and decayed as it grew. We watch answer quality slide, find the retrieval problem behind each drop, fix that layer in Qdrant, and prove the fix on Future AGI. Corpus: Gen-1 Pokémon from [PokéAPI](https://pokeapi.co). Full design in `CLAUDE.md`.

## Setup

```bash
uv sync                       # Python 3.12, pinned
cp .env.example .env          # fill in the five keys
```

`.env` needs `QDRANT_URL`, `QDRANT_API_KEY`, `ANTHROPIC_API_KEY`, `FI_API_KEY`, `FI_SECRET_KEY`.

## Build the demo collection

These commands touch the live Qdrant collections. `ingest.py` and `prep.py` build the show state; `verify_arc.py` intentionally changes it and must be followed by a restore.

```bash
uv run python ingest.py           # broken-on-purpose baseline (~10k points) in Qdrant Cloud
uv run python prep.py             # OFFLINE: add + backfill strong-dense, sparse, ColBERT
uv run python scaling_curve.py    # OFFLINE: the 500/2k/10k decay curve (opening hook)
uv run python check_baseline.py   # rehearsal gate: confirm each flaw shows red
uv run python verify_arc.py       # rehearsal gate: confirm each fix moves its metric (destructive)
```

`ingest.py` creates the flaws: small embeddings, duplicate and fragmented chunks, dense-only retrieval, and no payload index. It also builds the small `pokemon_viz` collection for the Web UI point-cloud beat and resets the agent's retrieval switch to the broken baseline. `prep.py` uses Qdrant 1.18's `create_vector_name` to add the fix vectors to the live collection with zero downtime, then backfills them, so the only live action on stage is flipping the agent's retrieval mode. `verify_arc.py` is destructive because dedup deletes points; re-run `ingest.py && prep.py` after it to restore the baseline.

## Run

```bash
uv run streamlit run app.py               # Pokédex chat UI + retrieval panel
uv run jupyter lab workshop.ipynb         # the fixes, one section each
```

## Layout

| Path | Role | On camera |
|---|---|---|
| `app.py` | Streamlit chat UI + retrieval panel | runs on screen |
| `agent.py` | LangGraph agent: Qdrant retrieval, grounding, citations | shown |
| `workshop.ipynb` | the fixes: dedup → embedding → hybrid+rerank → payload filter | shown |
| `ingest.py` / `prep.py` | broken ingestion / live-add + offline vector backfill | never |
| `scaling_curve.py` | offline 500/2k/10k decay curve → `data/scaling_curve.json` | never |
| `check_baseline.py` / `verify_arc.py` | rehearsal gates: flaws show red / fixes move | never |
| `helpers/` | PokéAPI, corpus, chunking, embeddings, UI, dedup | never |
| `data/golden_dataset.jsonl` | queries, expected answers, gold `doc_id`s | n/a |
| `RUNBOOK.md` | run of show: timings, expected numbers, checklist, fallbacks | n/a |

## The fixes

The agent's retrieval mode is a small file-backed switch (`agent.set_retrieval`). The notebook flips it; the Streamlit app reads it on each question and shows the active mode as a badge, so the audience returns to the chat UI and sees the agent answer better after each fix.

1. **Dedup**: delete duplicate points (`minilm` mode). Signal: duplicate rate in the top-5 (0.40 → 0.00 on the fix1 queries). The matching Future AGI dashboard read is being confirmed with Rishav — measured standalone, Chunk Utilization tracks the answer's use of context, not duplication (see `RUNBOOK.md`). Precision@K can't move honestly on this corpus; see `CLAUDE.md`.
2. **Embedding migration → know when *not* to migrate.** Qdrant 1.18 adds the bge vector to the live collection with zero downtime; flip to `bge` mode. On this corpus the bigger model *regresses* recall because the bottleneck was duplicates, not the model. The lesson (measure on your data before you commit) is the beat; the rollback is one line.
3. **Hybrid + rerank**: one multi-stage `query_points`: dense + sparse prefetch, RRF, ColBERT rerank (`hybrid` mode). Sparse means keyword-style matching; RRF means combining two ranked lists; ColBERT rerank means re-checking the best candidates token by token. The dense arm stays on MiniLM because hybrid scores the same with either model, which completes the fix-2 lesson. Signal on the 18 paraphrase queries: recall@5 0.06 → 0.94, NDCG@5 0.04 → 0.73, MRR 0.03 → 0.65 (sparse fusion starts the recovery, the ColBERT rerank surfaces the rest into the top-5).
4. **Cold-open close**: `is_current` payload filter removes the stale document. Dedup and hybrid don't fix this one: the stale chart matches the question's wording, so it wins retrieval until metadata excludes it.

Models: small `all-MiniLM-L6-v2` (384d), large `BAAI/bge-large-en-v1.5` (1024d), sparse miniCOIL, rerank `colbert-ir/colbertv2.0`. (mxbai was rejected: its high similarity floor collapsed under the duplicate crowding on this corpus.)

## Apply this to your own data

The workflow is the takeaway; the corpus is set dressing. To run it on your data: (1) build a golden set, meaning 20–50 real user queries with the documents that should answer them, keyed by a stable `doc_id` that survives re-ingestion; (2) trace your agent and read the retrieval-health metrics to find the failing layer before changing anything; (3) fix that layer in Qdrant: dedup at the source, A/B embedding models as named vectors on the live collection, upgrade to hybrid + rerank, and filter stale documents by payload; (4) re-run the same golden set after every change. A moving score on fixed queries proves the fix, and it also catches the fix that makes things worse (our fix #2).

## Notes

- Cluster must be Qdrant **v1.18+** for the live named-vector add (`create_vector_name`).
- Nintendo IP: fine for a live demo, don't publish the corpus as a downloadable artifact.
