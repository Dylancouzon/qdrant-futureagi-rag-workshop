# Run Of Show: 60 Minutes

Three surfaces: **App** (Streamlit chat), **NB** (`workshop.ipynb`), **FI** (Future AGI dashboard), plus **QUI** (Qdrant Cloud Web UI) for the point cloud. Times are ceilings.

| When | Beat | Who | Surface | The one thing that must happen |
|---|---|---|---|---|
| 0:00–0:05 | Intro: what the agent is, one working question | Dylan | App | Audience sees a correct, cited answer + the retrieval panel |
| 0:05–0:10 | Cold open: "Does Steel resist Ghost and Dark?" → wrong answer | Dylan | App | Panel shows the stale `typechart-steel-gen5` chunk winning |
| 0:10–0:14 | Tracing + judge calibration: why the numbers can be trusted | Rishav | FI | Cold-open trace on screen; custom judge marks it wrong |
| 0:14–0:19 | The decay curve: same queries, 500 → 2k → 10k points | Dylan | NB §1 | recall falls, duplicate rate rises: "growth exposed latent flaws" |
| 0:19–0:28 | Fix #1 dedup: dup-rate 0.40 → 0.00, 10.3k → 5.2k points | Dylan | NB §2 → QUI → FI | Point-cloud clusters thin out (`pokemon_viz`); duplicate rate hits zero (FI read: whatever Rishav confirmed at rehearsal) |
| 0:28–0:35 | Fix #2 migration: bge regresses recall 0.91 → 0.73, one-line rollback | Dylan | NB §3 → FI | The audience sees a fix FAIL and get caught by the eval: "measure before you migrate" |
| 0:35–0:43 | Fix #3 hybrid + rerank: recall 0.06 → 0.94, NDCG 0.04 → 0.73, MRR 0.03 → 0.65 | Dylan | NB §4 → App → FI | Sparse starts the recovery, ColBERT fixes the order; MiniLM stays (completes fix #2's lesson) |
| 0:43–0:48 | Cold-open close: `is_current` filter, re-ask in the app → correct | Dylan | NB §5 → App | "Dedup and hybrid didn't fix staleness — only metadata can" |
| 0:48–0:51 | Multi-hop trace (PROTECTED: never cut) | Rishav | NB §6 → FI | Two retriever spans from one compound question |
| 0:51–0:57 | Experiments view: before/after across all fixes | Rishav | FI | The full scoreboard, including fix #2's rolled-back regression |
| 0:57–1:00 | Close + Q&A buffer | both | n/a | The takeaway: measure → locate the layer → fix → re-measure |

**Running late? Drop in this order:** (1) shorten the 0:51 recap to 3 min, (2) compress fix #2 to flip → red number → rollback (3 min), (3) skip the second Web UI look after dedup. Keep the multi-hop beat and the cold-open close.

## Expected numbers (if a live number differs wildly, switch to the backup notebook)

- Decay curve: recall@5 0.78 → 0.62 → 0.28, dup-rate 0.21 → 0.33 → 0.38 (500 / 2k / 10k). Regenerate with `scaling_curve.py` whenever the golden set changes.
- Fix #1: duplicate rate 0.40 → 0.00; 10,325 → ~5,200 points; `pokemon_viz` 936 → ~180
- Fix #2: recall@5 MiniLM 0.91 vs bge 0.73 (the regression is the point)
- Fix #3 (n=18): recall 0.06 → 0.94, NDCG 0.04 → 0.73, MRR 0.03 → 0.65; fusion alone reaches recall 0.28, and the ColBERT rerank does the rest. The live scoring cell runs 18 queries × 2 modes in ~7 s with warm models (the setup cell's `warmup()` is what keeps it that fast).
- Cold open: stale gen5 chart first at baseline AND after dedup+hybrid; gen6 first only with the filter

## Pre-show checklist (T-60 min)

1. Fresh baseline if a rehearsal touched it: `uv run python ingest.py && uv run python prep.py` (slow; do this the night before, not at T-60).
2. `cat data/.retrieval_state.json` → must be `{"mode": "minilm", "current_only": false}` (ingest resets it; never trust a leftover).
3. `uv run python check_baseline.py` → every flaw red (fix1 dup@5 ≥ 0.4, fix3 gold missed).
4. Collections: `pokemon_workshop` ≈ 10,325 pts, `pokemon_viz` = 936 pts.
5. Start the app, let the model warm-up spinner finish, ask one throwaway question, confirm the badge reads `minilm`, then restart the app for a clean chat history.
6. Notebook: restart kernel, run ONLY the setup cell. Keep the executed backup notebook open in a second tab.
7. FI: logged in, project `pokedex-rag`, Experiments view pre-loaded. QUI: `pokemon_viz` Visualize tab pre-loaded with `{"limit": 1000}`.
8. Screen layout: App + notebook on the shared screen, FI dashboard ready to swap in; hide bookmarks bar, 125% zoom, notifications off.

## Fallbacks

- **Any notebook cell fails live** → switch to the executed backup tab, narrate from its output, debug never.
- **Cold open answers correctly** (parametric leak) → show the retrieval panel: the stale chunk still won retrieval; narrate "the generator got lucky, retrieval did not" and continue. The filter beat still lands.
- **Qdrant Cloud or Anthropic hiccup** → backup notebook carries every number; the app demo degrades to narrated screenshots (keep 3: wrong cold open, dup-crowded panel, corrected answer).
- **A score behaves oddly on FI** → Rishav narrates the local gold-label number from the notebook and moves on; reconcile in Q&A if asked.

## Rehearsal gates (before the dry run)

- `verify_arc.py`: every fix moves its number (DESTRUCTIVE: restore with ingest && prep after).
- Save the executed notebook copy from the successful rehearsal run as the backup.
- Click through `pokemon_viz` in the Visualize tab: duplicate clusters must be visible before dedup and visibly thinner after. Adjust `VIZ_POKEMON` in ingest.py if not.
- Confirm the dashboard triad behavior with Rishav. Measured via the `ai-evaluation` SDK (`model="turing_flash"`, context passed as one string: a list 500s): groundedness stays **green** through every retrieval failure (a grounded "I don't know" passes), context_relevance dips 0.7 → 0.5 on a dense miss but never collapses, and chunk_utilization scores the *answer's* use of context (0.0 whenever the agent refuses), not duplication itself. Registry identifiers confirmed: `context_relevance`, `chunk_utilization`, `chunk_attribution`, `groundedness`, `factual_accuracy`, `detect_hallucination`. The open question for Rishav: how the platform's dataset runs (vs standalone SDK calls) present these, and which one anchors each beat's dashboard read.
