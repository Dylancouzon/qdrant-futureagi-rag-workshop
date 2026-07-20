# Qdrant × Future AGI — Agentic RAG Workshop

## Project status (last updated 2026-07-20, second pass)

**The workshop is built and verified end-to-end** against the live Qdrant Cloud cluster
(v1.18.3). Read this block first, then `## Build outcomes` for the decisions that override
the original plan, then `README.md` to run it and `RUNBOOK.md` for the run of show. The
sections after that are the original design plan (kept for rationale; where they conflict
with Build outcomes, Build outcomes wins).

**What exists and runs** (all verified live):
- `helpers/` — PokéAPI corpus (1,515 docs), chunking, embeddings (+`warmup()`), UI, dedup, config.
- `ingest.py` — broken-on-purpose baseline (weak dense only, duplicates, tiny chunks, no index) + the small `pokemon_viz` collection (5 recognizable Pokémon, 936 pts) for the Web UI point-cloud beat + resets the retrieval state file.
- `prep.py` — offline: adds strong/sparse/ColBERT to the live collection (v1.18 `create_vector_name`) and backfills them.
- `agent.py` — LangGraph agent, file-backed retrieval mode switch (`minilm`/`bge`/`hybrid` + `current_only`) the notebook flips and the app reads. **Registers Future AGI tracing at import**, so the notebook, the Streamlit app, and rehearsal scripts all export traces.
- `app.py` + `helpers/ui.py` — Pokédex Streamlit chat UI + retrieval panel + retrieval-mode badge; warms all embedding models at boot. Passes a headless `AppTest` chat turn end-to-end.
- `workshop.ipynb` — the fixes, one section each; triad narration rewritten to match measured judge behavior (see below).
- `scaling_curve.py`, `check_baseline.py`, `verify_arc.py` — rehearsal gates (decay curve, flaws-show-red, fixes-move).
- `data/golden_dataset.jsonl` — 34 queries: cold_open 1, fix1 3, fix2 11, fix3 18, multi_hop 1. The 15 new fix3 queries were LLM-mined paraphrases of gen-1 flavor text, kept only if weak-dense missed top-5 AND hybrid recovered top-5 on the deduped copy (notes field records both ranks).
- `RUNBOOK.md` — run of show: beat timings, expected numbers, drop-order, pre-show checklist, fallbacks.

**Verified arc (all re-measured this pass):** decay curve recall 0.78→0.62→0.28,
dup-rate 0.21→0.33→0.38 at 500/2k/10k · dedup dup-rate 0.40→0.00 (10,325→~5.2k pts) ·
fix2 REGRESSION post-dedup: MiniLM 0.91 vs bge 0.73 ("measure before you migrate" +
zero-downtime rollback) · fix3 (n=18): recall 0.06→0.94, NDCG 0.04→0.73, MRR 0.03→0.65;
attribution: fusion alone reaches recall 0.28, ColBERT rerank does the rest · **hybrid's
dense arm is MiniLM** — measured identical to the bge arm (0.94 either way), which removes
the fix2/fix3 story contradiction ("keep the small model, change the strategy") · cold
open: the stale gen5 Steel chart outranks gen6 at baseline AND after dedup+hybrid (the
question inherits the stale vocabulary), so the `is_current` filter is genuinely the only
fix · baseline flaws all red in `check_baseline.py` (fix3 gold missed 17/18).

**Future AGI evals — measured self-serve via `ai-evaluation` (this pass):** registry
identifiers confirmed: `context_relevance`, `chunk_utilization`, `chunk_attribution`,
`groundedness`, `factual_accuracy` (it IS a built-in), `detect_hallucination`. Working SDK
recipe: `evaluate([...], input=…, output=…, context=<ONE STRING — a list 500s>,
model="turing_flash")`. Measured on real baseline retrievals: **groundedness stays green
(1.0) through every retrieval failure** (a grounded "I don't know" passes) —
retrieval-vs-generation separation works; **context_relevance dips 0.7→0.5 on a
dense-miss, never collapses** (Pokémon text is all topically similar); **chunk_utilization
scores the answer's use of context** (0.0 when the agent refuses), NOT duplication itself.
Notebook narration was rewritten to only claim these measured behaviors. Ask Rishav how
platform dataset runs differ from standalone SDK calls.

**Known accepted tension:** fragmentation (45-char chunks) is planted but never fixed —
dedup removes copies, not shredding. Load-bearing beats (cold open, multi-hop, fix3) answer
correctly anyway because chunks carry `[name]` tags and type-chart docs are never chunked;
the fix1 Charizard answer visibly says "cut off", which reads as broken data (good for the
before-state). If a beat ever needs whole flavor text, the fix is a re-chunk + re-backfill,
which is NOT stageable live.

**Cluster note:** `pokemon_dedup_test` (~5.2k pts) is a deduped copy of the baseline with
all vectors, used for offline scoring without touching the showtime collection. Rebuild by
scrolling unique (doc_id, chunk_index) points with vectors; delete freely.

**What's next:** browser click-through of the app + the `pokemon_viz` Visualize beat
(RUNBOOK gates) · Rishav confirms dashboard behavior of the triad on platform dataset runs
+ the Experiments view for the decay curve · run `verify_arc.py` once before the dry run,
then restore with `ingest.py && prep.py`.

## What this is

A live, one-hour joint technical webinar run by Dylan (Qdrant) and Rishav (Future AGI).
The story: an agentic RAG system that worked well on a small corpus and quietly decayed
as it grew. Three flaws were latent from day one; growth is what exposed them. We build
it, show the quality sliding as the collection grew, find why each metric slid, fix the
right layer, and prove each fix worked. Qdrant powers retrieval and every fix. Future AGI
traces and evaluates the agent throughout.

This repo holds the demo agent, the ingestion/corpus scripts, the "break it on purpose"
setup, and the shared golden dataset. Future AGI's tracing and eval config layer on top.

## Build outcomes (updated after the first full build + verification, 2026-07-20)

The plan below is the original design. What the live build proved, and the decisions that
override the plan where they conflict:

- **Cluster is Qdrant v1.18.3.** Named vectors are added to the live collection with
  `create_vector_name` (zero downtime); `ingest.py` ships a weak-dense-only baseline and
  `prep.py` adds + backfills strong/sparse/ColBERT.
- **Cold open is the Steel Ghost/Dark resistance question, not Magnemite.** Magnemite
  typing leaks from Haiku's memory (the biggest-risk prediction, confirmed). The obscure
  Steel fact does not leak. It works because the generator cites by *name* only (never
  generation or the gen-tagged doc_id), type-chart docs are not fragmented, and the stale
  Gen-5 chart is over-duplicated so it wins retrieval. Fix: a derived `is_current` payload
  filter. Verified: wrong answer at baseline → correct after the filter.
- **Two scored fixes carry the numbers: dedup (#1) and hybrid+rerank (#3).** Verified
  deltas (second pass): dedup duplicate-rate 0.40 → 0.00 (10.3k → 5.2k points); hybrid
  recall 0.06 → 0.94, NDCG 0.04 → 0.73, MRR 0.03 → 0.65 on the 18 dense-miss paraphrase
  queries (fusion alone reaches recall 0.28; the ColBERT rerank does the rest). The hybrid
  pipeline's dense arm is MiniLM — measured identical to the bge arm.
- **Fix #2 (embedding migration) is a cautionary beat, not a scored win.** On this corpus
  the weak model (MiniLM) already wins; migrating to a strong model REGRESSES recall
  (0.91 → 0.73), because the bottleneck was duplicates, not the model. The beat shows the
  zero-downtime migration + A/B + one-line rollback, and teaches "measure on your data
  before you commit." Strong model is `bge-large-en-v1.5` (mxbai collapsed under duplicate
  crowding). bge queries need a manual instruction prefix (FastEmbed omits it).
- **Fix #1 is scored on chunk_utilization / duplicate-rate, not Precision@K** (Precision@K
  cannot move honestly here — single-gold caps it, multi-gold entity queries start at 1.0).
- **Honest caveat (updated):** the corpus is easy for dense retrieval on entity queries,
  which is why fix #2 regresses. The golden set is now 34 queries; the 15 mined fix-3
  paraphrases were selected exactly where dense-only fails (selection criterion recorded
  per query in the notes field), so fix #3's 0.06 → 0.94 measures that class of query,
  not the whole corpus. Review the mined queries with Rishav before the show.

## North Star

One continuous walkthrough where the audience *sees* quality move. Every change we make
should show up as a number changing on Future AGI's dashboard and, where possible, as
something visible in the Qdrant UI. No reading dicts off a terminal. If a viewer can't
tell whether a fix worked by looking at the screen, we haven't built it right.

The audience is AI and ML engineers running agentic RAG in production, or dealing with
retrieval quality that got harder to explain as the system grew. They should leave with
a repeatable workflow: find why the agent degraded, fix the right layer, verify the fix
improved the agent and not just an isolated metric.

## Locked decisions

- **Framework: LangChain.** Qdrant retrieval gets auto-traced as retriever spans through
  Future AGI's traceAI LangChain instrumentation, so no manual span work on stage.
- **Corpus: Pokémon, via PokéAPI (https://pokeapi.co).** Free, open API. Chosen for fun,
  instantly obvious right/wrong answers, and a *real* outdated-doc conflict: Pokémon
  typings, base stats, and the type-effectiveness chart genuinely changed across
  generations, so the same "document" has different correct answers by generation. Sprites
  make the Qdrant point cloud fun to look at. Caveat: Nintendo IP, fine for a live demo,
  be careful about publishing the corpus as a downloadable artifact afterward.
- **Three scored fixes, in order: dedup → embedding migration → hybrid + reranking.** Each
  maps to a distinct Future AGI metric so the dashboard tells three different stories.
- **Multi-hop is a trace-only bonus beat, not a scored fix.** The agent decomposing a
  compound question into two retrieval spans is the "this is an agent, not a single-shot
  retriever" moment; it lives in Future AGI's trace view, with no scored delta to
  engineer. Making it a scored fix needs no-clean-filter query design plus unverified
  trajectory evals — too much machinery for the "agentic" label. See the bonus beat below.

## Biggest risk: every LLM already knows Pokémon

Pokémon is heavily represented in training data. If retrieval returns a stale Gen-1 doc,
a modern generator may still answer correctly from parametric memory — which breaks the
cold open and quietly degrades all three fixes, because better retrieval stops mattering
when the model already knows the answers. Mitigations, all required:

- A hard grounding system prompt: answer only from retrieved documents, cite them.
- Bias golden questions toward facts models don't reliably memorize (per-generation
  type-chart resistances, obscure flavor-text details) over headline facts every model
  knows. (Past base stats would qualify but aren't exposed by PokéAPI.)
- Rehearsal must explicitly verify that wrong retrieval produces wrong answers. If the
  generator still leaks parametric knowledge, switch to a smaller model — a weaker
  generator makes this demo better.
- The cold open uses Magnemite's typing (Electric/Steel) for its visual punch, but that
  is the single most-memorized fact in the corpus, so leakage is likeliest exactly there.
  Rehearse it hard, and hold a per-generation type-chart *resistance* question (Steel
  resisting Dark/Ghost pre-Gen-6) as an on-stage fallback — obscure enough that wrong
  retrieval reliably yields a wrong answer.

## The arc

1. **Show the agent.** What it is, what it's supposed to do, a Pokémon query that works.
2. **Cold open on the pain (conflicting docs).** Ask something whose answer changed across
   generations (primary: Magnemite typing; backup: a per-generation Steel resistance if
   the model leaks parametric knowledge — see biggest-risk section). The agent retrieves
   the stale doc and answers wrong in an obviously funny way — the same document has a
   different right answer by generation, and the agent grabbed the outdated one. Scored
   with a custom judge against
   the current expected answer, NOT `groundedness` (see note below). `factual_accuracy`
   is not a confirmed built-in eval name — build this as a Future AGI custom judge
   (CustomLLMJudge) with Rishav, which doubles as a platform showcase and feeds his
   calibration segment.
3. **Measure (Future AGI).** The dashboard lights up. Open on a scaling stress test, not a
   fake timeline: run the same golden set against the collection at 500 / 2k / 10k points
   and plot how retrieval decays as the haystack grows. Frame it as exactly what it is — a
   controlled experiment ("watch the same queries get worse as we scale"), never six
   months of history. Whichever of Precision@K, Recall@K, NDCG@K/MRR actually slide (see
   the rehearsal gate) become the curve; the runs are pre-computed offline. This is the
   honest "it decays as it grows" proof. Scores then point to which layer to fix first.
4. **Fix the right layer (Qdrant).** One issue at a time.
5. **Measure again.** Watch the metric move before moving on. All "before" scores are
   pre-run before the session. Whether "after" scores run live is decided in rehearsal:
   time one full batch (30 queries × the metrics). If it's fast (~20s), run it live; if
   it's minutes, pre-bake the "after" scores too and reveal on click. Either way the
   number moves on screen — dead air is the risk we're buying down, not authenticity.
6. **Repeat** for each of the three scored fixes.
7. **Close the cold-open loop: payload filter.** Come back to the wrong answer from the
   open and fix it with one line — filter on `generation` in the payload at query time.
   Filtered vector search is Qdrant's most differentiated capability; this resolves the
   arc and adds a fourth Qdrant fix with zero overlap with the dedup visual.
8. **Multi-hop in the trace view (protected — Future AGI's showcase moment).** Ask a
   compound question and let the audience watch the agent decompose it into two retrieval
   spans in Future AGI's trace. This is the "it's an agent, not a single-shot retriever"
   proof, with no scored delta to engineer. Keep it to ~2 minutes; if the hour runs long,
   trim the closing recap or narration elsewhere, not this beat. (If a score ever drops
   for a reason that is NOT retrieval — e.g. the agent's own query rewriting — say so in
   one sentence here; it never needs its own beat.)
9. **Compare** before and after across all changes in Future AGI's Experiments view.

The handoff cue each time is Future AGI's diagnostic triad: `context_relevance`,
`chunk_utilization`, `groundedness`. Together they tell us whether a failure is a
retrieval problem (Dylan's to fix in Qdrant) or a generation problem. The gold-labeled IR
metrics (Precision/Recall/NDCG/MRR) then quantify the retrieval fix — but they need gold
labels the audience won't have, so the reproducible skill is the triad read. At every
handoff Rishav says the diagnosis out loud as an inference ("Precision down, Recall
steady — that pattern is duplicates, not a weak model"). That spoken reasoning, not the
planted flaw, is what the audience takes home.

## Division of labor

- **Qdrant / Dylan**: builds the agent, owns the retrieval layer and every fix
  (embedding migration, dedup, hybrid + reranking, top-k), owns the Qdrant UI
  visuals.
- **Future AGI / Rishav**: owns instrumentation (traceAI, ~a few lines), eval
  definitions, running evals on the Future AGI platform, reading the scores live, and a
  ~2-minute deeper segment early on: how the judge is calibrated and why the scores are
  trustworthy. The whole session hinges on the audience believing the numbers, so this
  goes up front.
- **Shared**: the golden dataset of test queries.

## Build and dataset sequencing (agreed with Future AGI)

1. Dylan builds the working agent (LangChain + Qdrant, broken on purpose) and shares the
   repo.
2. Dylan and Rishav jointly write the test queries and known-good answers against the
   working system.
3. Rishav configures and runs the evals on the Future AGI platform.

The dataset is a fixed set of queries with known-good answers, run before and after every
fix. Same questions every time so a moving score proves the fix worked, not that the test
got easier. It must actually exercise the flaws we build in, or the evals stay green and
the story dies. For the IR metrics (MRR, NDCG@K, Recall@K) each query also needs its
relevant "gold" chunk(s) labeled; decide with Rishav how many of the ~30–50 queries to
label, since that's the real prep cost.

**Gold labels are doc-level, never point-level.** Fix #1 re-ingests the collection and
fix #2 re-embeds it — point-ID-based labels would silently break between the before and
after runs and invalidate the comparison. Every chunk carries a stable `doc_id` in its
payload (e.g. `magnemite-gen2-types`) from the first ingestion script onward, gold labels
reference `doc_id`, and IR metrics are computed against it. Ask Rishav how the platform
expects gold chunk labels to be formatted — the docs describe a ground-truth "base
column" but not chunk-level labeling.

## What we're building

An **agentic** RAG system, not a single-shot retriever. The agent rewrites queries,
decides when to retrieve, may do multi-hop retrieval (type-effectiveness chains, evolution
lines), and cites sources. This opens up agentic failure modes (tool decisions, query
rewriting, multi-hop) on top of plain retrieval quality.

The agent gets a **chat UI (Streamlit)** for the audience-facing beats: a chat pane plus
a retrieval panel showing, per question, the retrieved chunks with sprite, `doc_id`,
generation tag, similarity score, and rank. The panel makes every failure visible before
a score confirms it — duplicates crowding the top-k, a gen-1 tag on the winning chunk,
the right chunk ranked 7th — and visibly changes after each fix. Hard boundary: the UI
never displays eval scores; answers and retrieved chunks live in our UI, judgments live
on Future AGI's dashboard, or the two-product handoff dies. Styling: light, high
contrast, Pokédex-themed, readable from across a room — never the default dark theme.

Three surfaces, three roles: chat UI = experience the failure, notebook = perform the
fix (the code on screen), Future AGI dashboard = prove it worked.

## Code is part of the show

The implementation gets shown, so demo-facing code reads like documentation:

- Anything on screen (notebook cells, the agent definition) contains Qdrant and Future
  AGI calls verbatim and nothing else. A viewer should see `query_points`, the
  instrumentor setup, and the eval hooks — not plumbing.
- PokéAPI fetching, chunking, payload formatting, UI code, and the break-it-on-purpose
  ingestion live in helper modules the camera never opens.
- No cleverness in the visible path: explicit arguments over config indirection, short
  cells, one concept per cell.

Framework is locked (LangChain); in practice that means **LangGraph** for a multi-hop
tool-using agent — the same traceAI instrumentor covers LangGraph with a documented
multi-step agent example, so the auto-tracing premise holds.

## Build decisions (defaults — change here, not ad hoc in code)

- **Qdrant**: Qdrant Cloud cluster (it's the product on stage; Web UI included). Client
  via `qdrant-client`. Env: `QDRANT_URL`, `QDRANT_API_KEY`.
- **Embeddings**: all via FastEmbed, no embedding API keys. Weak model
  `sentence-transformers/all-MiniLM-L6-v2` (384d), strong model
  `mixedbread-ai/mxbai-embed-large-v1` (1024d), reranker `colbert-ir/colbertv2.0` as a
  MAX_SIM multivector, plus a sparse model via FastEmbed for fix #3's hybrid prefetch
  (miniCOIL — Qdrant-differentiated — or BM25; confirm the exact FastEmbed identifier at
  build). Rehearsal must confirm the weak→strong Recall@K gap is real on our golden
  queries; if it isn't, pick a weaker weak model, not easier queries.
- **Generator**: Anthropic `claude-haiku-4-5` via `langchain-anthropic`, with the strict
  grounding prompt. Small is deliberate: fast on stage, and less prone to answering from
  memorized Pokémon knowledge instead of retrieved docs. If its tool-calling in the
  LangGraph agent proves shaky in rehearsal, step up to `claude-sonnet-5`.
- **Corpus**: Gen 1's 151 Pokémon. Per Pokémon: flavor text per generation (the semantic
  queries target these), types including `past_types`, base stats. Plus one type-chart
  doc per generation. The scaling test grows this to ~10k points with injected duplicates;
  the Qdrant Web UI point-cloud beat runs on a separate small collection, sized so its
  Visualize sample is near-complete and the duplicate clusters show honestly.
- **Payload schema (every point)**: `doc_id` (stable, e.g. `magnemite-gen2-types`),
  `name`, `generation`, `doc_type` (`flavor|types|stats|type_chart`), `sprite_url`,
  `text`. Gold labels and the payload-filter fix both depend on this schema — it is not
  optional.
- **Broken-on-purpose staging**: `ingest.py` ships the broken state by default
  (duplicates, tiny chunks, weak embeddings, no filter). Each fix is applied live as
  notebook cells against the running collection — never by re-running a "fixed" ingest,
  or the audience suspects a swap.
- **Repo layout**: `app.py` (Streamlit chat UI), `agent.py` (LangGraph agent — camera
  visible, Qdrant + traceAI calls verbatim), `ingest.py` (broken ingestion), `helpers/`
  (PokéAPI fetching, chunking, UI plumbing — camera never opens), `workshop.ipynb` (the
  fixes, one section per fix), `data/golden_dataset.jsonl` (query, expected answer, gold
  `doc_id`s).
- **Env**: `.env` with `QDRANT_URL`, `QDRANT_API_KEY`, `FI_API_KEY`, `FI_SECRET_KEY`
  (Future AGI platform credentials), `ANTHROPIC_API_KEY`; `.env.example` checked in.

## The three scored fixes

Ship the agent already broken in three ways, each mapping to one clean Qdrant fix and a
distinct primary metric. Before the session, confirm on the Future AGI platform that each
flaw actually shows up red. If a fix lands and no metric moves, the narrative dies.

1. **Duplicate and fragmented chunks → dedup the collection.**
   *How it decays with growth:* re-ingestion and overlapping crawls pile up duplicate and
   fragmented chunks over time, so the top-k fills with copies and Precision@K slides.
   Primary metric `Precision@K`, secondary `chunk_utilization`. Precision@K is
   deterministic and computed from gold labels, but it only moves the right way if the
   duplicated docs are **distractors** crowding gold docs out of the top-k. Duplicate the
   *gold* doc and Precision@K goes UP (more relevant hits in top-k), so dedup would drop
   it on stage. Build rule: over-chunk with a tiny chunk size and re-ingest overlapping
   copies of the *distractor* docs, keep each gold doc single-copy, run no dedup, and
   confirm Precision@K is actually red on the baseline before promoting it. Chunk
   Utilization's semantics on duplicates are unverified: if the judge marks the used text
   as "utilized" in every copy it stays green, so verify it on the baseline too.
   Deterministic bug, easiest to grasp, and the best Qdrant UI moment: dense clusters that
   visibly thin out after dedup. Keep top-k small enough that duplicates actually crowd
   out unique chunks. (Qdrant also has native MMR for query-time diversity — worth a
   one-sentence mention on stage, but dedup at the source is the fix.)

2. **Stale / weak embedding model → zero-downtime migration to a stronger model.**
   *How it decays with growth:* the weak model doesn't change, but the corpus gets denser.
   A 384-dim model separates 500 docs fine; at 10k near-duplicate flavor-text chunks the
   top-k fills with near-misses it can't tell apart, so Recall@K on the same golden queries
   decays as N grows while the strong 1024-dim model holds. This is the "both problems"
   fix: mediocre on day one, and growth is what made it hurt.
   Primary metric `Recall@K`, secondary `context_relevance`. Start on a small dated model.
   The golden queries must be genuinely semantic (paraphrase, synonyms, little keyword
   overlap), or a weak model finds them anyway and the metric won't move. On this corpus
   that means targeting **Pokédex flavor text**: Pokémon queries are entity-heavy, and
   even weak models retrieve named entities, while queries that dodge the name read as
   rigged. Ingest flavor text per Pokémon per generation and write this fix's golden
   queries exclusively against it ("a Pokémon that eats dreams" → Drowzee). If rehearsal
   shows Recall@K barely moves, demote this fix rather than ship a flat chart. The
   load-bearing claim is that the weak→strong gap *widens with corpus size* — verify the
   differential on the golden queries at the three collection sizes. If the gap doesn't
   widen, this fix reverts to a flat day-one framing and only dedup + reranking carry the
   "over time" curve. Migration
   pattern: named vectors on the same collection (v1.18+) per the official
   embedding-model-migration tutorial — schema-only add, dual-write, backfill, flip
   `using`, drop the old vector. Pre-bake the backfill offline before the session; the
   only live action on stage is the one-line `using` flip and the re-measure, so the beat
   stays fast and the slow backfill never runs on camera.

3. **Dense-only, no reranking → upgrade to Qdrant's recommended hybrid + rerank pipeline.**
   The baseline retrieves with one dense query and no reranking. The fix is the canonical
   multi-stage Qdrant Query API call: prefetch dense + sparse, fuse with RRF, then rerank
   the fused candidates with the ColBERT late-interaction multivector — one `query_points`
   call, tighter top-k.
   *How it decays with growth:* the chunk that ranked 2nd against 500 competitors ranks
   8th against 10k, so NDCG@K and MRR slide; sparse also recovers entity/keyword matches
   the dense model loses as similar names crowd the space.
   Primary metrics `NDCG@K` and `MRR` (rank-sensitive), secondary `Recall@K` and
   `chunk_utilization`. Engineer queries where the right chunk is retrieved but ranked
   ~6–9 of 10, plus a few entity+semantic queries pure dense misses so the sparse half
   earns its place. Attribution caveat: hybrid lifts recall and rerank lifts rank, so the
   combined jump bundles two levers — to attribute cleanly, show the sparse prefetch and
   the rerank as two sub-cells in rehearsal. Pre-index the sparse vectors offline; the live
   action is just switching the query to the multi-stage call. Closes on Qdrant's most
   differentiated capability, the universal Query API.

## Not among the three scored fixes (deliberate)

- **Conflicting / outdated docs**: used as the cold-open live-failure beat and resolved
  at the end with the payload-filter fix (arc step 7), not a scored fix. Risk: an answer
  from the stale doc is still technically "grounded" (just in the wrong version), so
  `groundedness` can stay green. Score it with a custom judge against the current
  expected answer instead (`factual_accuracy` is unconfirmed as a built-in — confirm the
  exact eval with Rishav). Its natural Qdrant visual (near-duplicate points disappearing)
  overlaps with the dedup story, so the fix visual is the filter + the corrected answer,
  not the point cloud.
- **Multi-hop retrieval**: the trace-only bonus beat (arc step 8), not a scored fix. It
  proves the system is agentic by showing the agent decompose a compound question into
  two retrieval spans in Future AGI's trace. A *scored* multi-hop fix was considered and
  dropped: its natural Qdrant lever (Discovery API steering hop 2 by example) collapses
  into the payload-filter close whenever hop 2 has a clean filter key, and its metrics
  would lean on Future AGI trajectory evals (Trajectory Match, Tool Call Accuracy) whose
  schemas are unconfirmed. Per-hop RAG metrics on the intermediate span plus a
  CustomLLMJudge on the final answer are the confirmed way to score it if we ever revive
  it — confirm with Rishav first.
- **Bad query rewriting**: the fix lives in the agent, not Qdrant, so it breaks the "every
  fix is Qdrant" premise. Not a beat — at most one spoken sentence during the multi-hop
  trace view, noting a drop that isn't retrieval's fault.

## Failure modes and what detects them

| Failure mode | Layer | Future AGI signal |
|---|---|---|
| Weak/stale embeddings retrieve poor chunks | retrieval | `Recall@K`, `context_relevance` low |
| Duplicate / fragmented chunks | retrieval | `Precision@K` low (`chunk_utilization` uncertain on duplicates — verify) |
| No reranking, relevant chunk ranked low | retrieval | `NDCG@K`, `MRR` low (lost-in-the-middle) |
| Dense-only misses exact entity/keyword matches | retrieval | `Recall@K` low on entity queries (hybrid recovers) |
| Conflicting / outdated docs | data/retrieval | custom judge fails vs current answer |
| Bad query rewriting | agent | `context_relevance` drops despite a good index |
| Wrong retrieval decision (retrieves when it shouldn't, or skips) | agent | tool-call spans |
| Multi-hop breakdown | agent | session / trace view |
| Hallucinated citations | generation | `chunk_attribution` fail |
| Answer ignores good context | generation | `chunk_utilization`, `completeness` |
| Hallucination / unsupported claims | generation | `faithfulness`, `groundedness` |
| Latency / cost creep | system | per-step tokens and latency in tracing |

Rule of thumb from Future AGI's own docs: low `context_relevance` + low
`chunk_utilization` means the retriever is fetching irrelevant chunks, so the fix is in
Qdrant (embeddings, reranking, top-k). Good `context_relevance` but low `chunk_utilization`
or failing `groundedness` points at the generation side.

## Corpus facts (verified against the live PokéAPI, July 2026)

- **`past_types` — verified.** On `/pokemon/{id}`. Magnemite and Magneton: pure Electric
  in Gen 1, Electric/Steel since Gen 2 — the cleanest cold-open example. Also available:
  Clefairy/Clefable, Jigglypuff/Wigglytuff, Mr. Mime (gained Fairy/psychic-fairy in
  Gen 6, recorded as a Gen 5 snapshot). Marowak has no type change.
- **Flavor text per generation — verified.** `flavor_text_entries` on
  `/pokemon-species/{id}`, English entries per game version (~30+ per Gen 1 species),
  `version.name` maps entries to generations. Drowzee Red/Blue: "Puts enemies to sleep
  then eats their dreams." — the fix-#2 semantic queries work.
- **Type chart per generation — verified.** `past_damage_relations` on `/type/{id}`.
  Steel's Gen 5 snapshot includes Dark and Ghost resistances, current does not (lost in
  Gen 6); Fairy introduced Gen 6. "What resists Steel?" has a clean generation-dependent
  answer.
- **Base-stat history — NOT available.** No `past_stats` field; the API only serves
  current stats. Base-stat rebalances are out of the corpus — don't build queries on
  them.

## Expected outcomes

- Every fix produces a visible, verifiable score improvement.
- A clear before/after comparison across all changes at the end (Experiments view).
- A repeatable diagnostic workflow the audience can take home: measure → locate the
  failing layer → fix it → verify against the same eval set.
- A clean two-product handoff that never has one presenter building the other's part.

## Visual bar

- Qdrant Web UI: chunks as points, duplicates as tight clusters, dedup thinning them out,
  retrieval hits highlighted per query. Pokémon sprites make this genuinely fun. Caveat:
  the Visualize tab samples the collection (unofficial reports say ~500 points default,
  browser struggles above ~10k with t-SNE/UMAP) — size the demo collection so duplicates
  actually appear in the sample, and test this before betting the beat on it.
- Future AGI dashboard on screen alongside so scores move the moment a fix lands.
- Chat UI (Streamlit) with the retrieval panel — the failure is visible in the chunks
  before any score confirms it. No eval scores here, ever.
- Notebook with rich inline output showing the fix and its retrieval effect (changed
  chunks, point cloud, timings), not printed dicts — and never eval scores; those stay on
  Future AGI's surface.
- The scaling stress test: the golden set scored offline at 500 / 2k / 10k points,
  plotted as retrieval decaying while the haystack grows — presented as a controlled
  experiment, never a fake timeline. This is the opening hook (arc step 3); each fix later
  bends its curve back up.
- A persistent scoreboard in Future AGI's Experiments view — metrics with before/after
  and a running delta — on screen alongside, never rendered in our notebook or chat UI.

## Still open

- Agent structure and ingestion scripts (framework locked, build not started).
- Exact Pokémon and questions for the golden dataset (built jointly with Rishav).
- How many queries to label with gold chunks for IR metrics.
- A pre-session baseline run to confirm each flaw shows up red on the Future AGI platform,
  and the offline decline-curve runs: score the golden set at ~500 / 2k / 10k points to
  produce the scaling-test curve. Cheapest build is to ingest in three stages and run the
  golden set after each. The curve is only honest if all three metrics actually slope down
  across the sizes — confirm Precision@K, Recall@K, and NDCG@K/MRR each decline, and that
  the weak-embedding gap widens. Any metric that stays flat drops off the curve rather
  than shipping a line that doesn't move.
- With Rishav (confirmations, not blockers — each has a self-serve path):
  - Cold-open eval: we build the custom judge assumption in; the dataset carries an
    `expected_answer` column either way.
  - Gold-label format: `data/golden_dataset.jsonl` is our canonical format (query,
    expected answer, gold `doc_id`s); platform format is a small converter later.
  - Eval latency: measure ourselves with the `ai-evaluation` SDK once FI keys are in
    (time 5 queries × 4 metrics, extrapolate) instead of waiting for an answer.
- Logistics: date, screen-share driver, showing Qdrant UI and the Future AGI dashboard
  side by side cleanly, one rehearsal of the handoffs.

## Reference

Future AGI packages: `ai-evaluation` (evals, `from fi.evals import evaluate`),
`fi-instrumentation-otel` + `traceAI-langchain` (tracing), `futureagi` (platform SDK incl.
datasets/experiments). Auth via `FI_API_KEY` + `FI_SECRET_KEY`. Key docs: RAG Evaluation
cookbook, Hallucination Detection cookbook, Experiments, Built-in Evals reference at
docs.futureagi.com.

Metric names in this doc are shorthand. The platform's confirmed built-in RAG evals use
Title Case display names (Context Relevance, Chunk Utilization, Chunk Attribution,
Groundedness, Completeness, Detect Hallucination, Recall@K, Precision@K, NDCG@K, MRR,
Hit Rate). Verify exact identifiers with Rishav before they go on a slide.

Agentic and conversation evals also exist by name (Tool Call Accuracy, Trajectory Match,
Step Count, Task Completion, Conversation Coherence) but their input schemas aren't in the
public docs — treat them as "confirm with Rishav," not as something to script a scored
beat around. Evals run per-span within a trace, so per-hop RAG scoring is possible in
principle; CustomLLMJudge takes arbitrary named fields (so a full trajectory can be fed
in) and is the confirmed path for any bespoke multi-step check.
