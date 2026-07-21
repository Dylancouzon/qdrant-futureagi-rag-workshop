# Qdrant × Future AGI: Agentic RAG Workshop

Live workshop demo for an agentic RAG system whose retrieval quality gets worse as the corpus grows. The flow: show the failure in the app, diagnose it in Future AGI, fix retrieval in the Qdrant vector search engine, and measure again.

Corpus: all 1,025 Pokémon from [PokéAPI](https://pokeapi.co), with realistic re-crawl duplication and one stale type-chart document.

- Run-of-show, expected numbers, and fallbacks: `RUNBOOK.md`
- Design notes and measurement history: `CLAUDE.md`

## Setup

```bash
uv sync
cp .env.example .env
```

Fill in:

```text
QDRANT_URL
QDRANT_API_KEY
ANTHROPIC_API_KEY
FI_API_KEY
FI_SECRET_KEY
```

Create a free cluster at [Qdrant Cloud](https://cloud.qdrant.io) (v1.18+) and add its URL and API key to `.env`.

## Build Or Restore

On a fresh cluster:

```bash
uv run python ingest.py   # intentionally flawed baseline + pokemon_viz
uv run python prep.py     # backfill fix vectors, then snapshot both collections
```

After a rehearsal, notebook run, or destructive verification:

```bash
uv run python snapshot.py restore
```

`restore` uses the cluster snapshot created by `prep.py` when it can. If that is missing, it uses the newest local `data/{collection}-*.snapshot`. Use `snapshot.py download` to save cluster snapshots locally and `snapshot.py backup` to snapshot the current cluster state. Snapshot files are gitignored.

After restore, confirm the app starts from the broken baseline:

```bash
cat data/.retrieval_state.json
# {"mode": "minilm", "current_only": false}
```

## Run

```bash
uv run streamlit run app.py
```

Open `workshop.ipynb` in your IDE and select the `.venv` kernel.

Use the app for audience-facing questions and the notebook to apply each fix. The app reads the retrieval switch on every question, so notebook changes show up on the next app request.

## Future AGI Handoff

Tracing is already wired in `agent.py`:

```python
trace_provider = register(project_type=ProjectType.OBSERVE, project_name="pokedex-rag")
LangChainInstrumentor().instrument(tracer_provider=trace_provider)
```

With `FI_API_KEY` and `FI_SECRET_KEY` set, the app, notebook, and rehearsal scripts send traces to the `pokedex-rag` project. Qdrant retrieval appears as retriever spans.

To create a scored run, send the golden set through the traced agent:

```bash
uv run python run_golden.py
```

It uses the agent's current retrieval state. Run it once per stage (baseline, dedup, bge, hybrid, filter), then compare the runs in Experiments. It also writes `data/golden_run-{mode}.jsonl` with each answer and its `retrieved_context`: the exact text the model read, as one string, ready for `fi.evals.evaluate(context=...)`.

Shared eval dataset: `data/golden_dataset.jsonl`.

| Field | Meaning |
|---|---|
| `query` | agent input |
| `expected_answer` | answer used by the cold-open custom judge |
| `gold_doc_ids` | stable doc-level labels for IR metrics |
| `exercises` | target beat: `cold_open`, `fix1_dedup`, `fix2_embedding`, `fix3_hybrid`, `multi_hop` |
| `notes` | selection evidence and measured ranks |

Recommended dashboard anchors:

| Beat | Platform read |
|---|---|
| Cold open | custom LLM judge vs `expected_answer` |
| Fix #1 dedup | notebook duplicate rate + retrieval panel / point cloud (`chunk_utilization` does not score duplication) |
| Fix #2 embedding migration | `Recall@K` + `context_relevance` |
| Fix #3 hybrid + rerank | `NDCG@K`, `MRR`, `Recall@K` |
| Handoffs | `context_relevance` + `chunk_utilization` + `groundedness` |

Measured SDK behavior so far: `groundedness` can stay green during retrieval failures because a grounded refusal passes; `context_relevance` dips on dense misses but does not collapse; `chunk_utilization` measures how the answer uses retrieved context, not whether retrieval was duplicated.

Open Future AGI integration items:

1. Confirm how platform dataset runs present the triad versus standalone SDK calls.
2. Confirm the platform gold-label format for IR metrics; this repo can convert from the JSONL above.
3. Set up the Experiments view for the before/after scoreboard at the 0:51 runbook beat.

## Fixes

The retrieval mode is controlled by `agent.set_retrieval(...)` and saved in `data/.retrieval_state.json`.

1. **Dedup**: delete duplicate points. Top-5 duplicate rate drops 0.67 → 0.00; `pokemon_webinar` shrinks 22.9k → 8.4k points.
2. **Embedding migration**: add `bge-large` as a named vector, A/B against MiniLM, then commit. Recall on lookalike-species queries moves 0.64 → 1.00.
3. **Hybrid + rerank**: dense + sparse prefetch, RRF fusion, and ColBERT rerank in one `query_points` call. Recall on hard paraphrase queries moves 0.78 → 0.89.
4. **Freshness filter**: `is_current` removes the stale type-chart document that better ranking alone cannot beat.

Local FastEmbed models: `all-MiniLM-L6-v2`, `BAAI/bge-large-en-v1.5`, `Qdrant/minicoil-v1`, `colbert-ir/colbertv2.0`.

## Repo Map

| Path | Role |
|---|---|
| `app.py` | Streamlit chat UI + retrieval panel |
| `agent.py` | LangGraph agent, Qdrant retrieval, Future AGI tracing, grounding |
| `workshop.ipynb` | live fixes, one section each |
| `ingest.py` / `prep.py` | flawed ingest, vector backfill, snapshots |
| `run_golden.py` | golden set through the traced agent, once per stage |
| `snapshot.py` | restore, download, or back up show state |
| `verify_arc.py` | rehearsal gate; destructive unless run with `--baseline-only` |
| `scaling_curve.py` | regenerates the decay chart |
| `helpers/` | corpus, chunking, embeddings, UI helpers |
| `data/golden_dataset.jsonl` | queries, expected answers, gold doc labels |

## Notes

- `traceAI-langchain` requires `langchain<0.4`, so the agent uses `langgraph.prebuilt.create_react_agent`. Move to `langchain.agents.create_agent` when Future AGI supports LangChain 1.x.
- Pokémon/Nintendo IP is fine for the live demo. Do not publish the corpus as a downloadable artifact.
