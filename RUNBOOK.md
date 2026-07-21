# Run Of Show: 60 Minutes

Three surfaces: **App** (Streamlit chat), **NB** (`workshop.ipynb`), **FI** (Future AGI dashboard), plus **QUI** (Qdrant Cloud Web UI) for the point cloud. Times are ceilings.

| When | Beat | Who | Surface | The one thing that must happen |
|---|---|---|---|---|
| 0:00–0:05 | Intro: what the agent is, one working question | Dylan | App | Audience sees a correct, cited answer + the retrieval panel |
| 0:05–0:10 | Cold open: "Does Steel resist Ghost and Dark?" → wrong answer | Dylan | App | Panel shows the stale `typechart-steel-gen5` chunk winning |
| 0:10–0:14 | Tracing + judge calibration: why the numbers can be trusted | Rishav | FI | Cold-open trace on screen; custom judge marks it wrong |
| 0:14–0:19 | The decay curve: same queries as the Pokédex grew Gen 1 → Gen 4 → full dex | Dylan | NB §1 | recall falls 0.67 → 0.39 as real lookalike species pile in: "growth exposed latent flaws" |
| 0:19–0:28 | Fix #1 dedup: dup-rate 0.67 → 0.00, 22.9k → 8.4k points | Dylan → Rishav | NB §2 → QUI → FI | "Tell me the Pokedex entry for Gengar" goes from one chunk ×5 to five distinct docs. Narrate 0.67 → 0.00 as "the redundancy is gone — look what fills the freed slots" (the zero is guaranteed by the delete; the panel and point cloud are the evidence). Rishav reads the FI side |
| 0:28–0:35 | Fix #2 migration: A/B decides — recall 0.64 → 1.00, commit to bge | Dylan → Rishav | NB §3 → FI | The eval decides a migration live: the 384d model stopped separating Pikachu from its ten clones. Say the selection out loud: "these are the queries we mined where the weak model fails — entity questions were already at 1.0." Rishav speaks the diagnosis |
| 0:35–0:43 | Fix #3 hybrid + rerank on top of bge: recall 0.83 → 1.00, NDCG 0.63 → 0.82 | Dylan → Rishav | NB §4 → App → FI | Sparse widens the candidate pool, the ColBERT rerank turns it into top-5 wins. **Rishav delivers the counter-intuitive number:** fusion without rerank scores WORSE at top-5 (0.72) than pure dense (0.83) — it's a pipeline, and that's why you measure each stage |
| 0:43–0:48 | Cold-open close: `is_current` filter, re-ask in the app → correct | Dylan | NB §5 → App | "Dedup, the bigger model, and hybrid all failed to fix staleness — only metadata can" |
| 0:48–0:51 | Multi-hop trace (PROTECTED: never cut) | Rishav | NB §6 → FI | Two retriever spans from one compound question |
| 0:51–0:57 | Experiments view: before/after across all fixes | Rishav | FI | The full scoreboard across the four fixes |
| 0:57–1:00 | Close + Q&A buffer | both | n/a | The takeaway: measure → locate the layer → fix → re-measure |

**Running late? Drop in this order:** (1) shorten the 0:51 recap to 3 min, (2) compress fix #2 to flip → green number → commit (3 min), (3) skip the second Web UI look after dedup. Keep the multi-hop beat and the cold-open close.

## Expected numbers (verified 2026-07-21 on the full-dex corpus; if a live number differs wildly, switch to the backup notebook)

- Decay curve: recall@5 0.67 → 0.45 → 0.39, dup-rate@5 0.44 → 0.51 → 0.52 (Gen 1: 1,314 pts / Gen 1–4: 8,351 / full: 22,946). Regenerate with `scaling_curve.py` whenever the golden set changes.
- Fix #1: duplicate rate 0.67 → 0.00; 22,946 → 8,416 points; `pokemon_viz` 240 → 95
- Fix #2 (n=14): recall@5 MiniLM 0.64 → bge 1.00 (the full dex made the model the bottleneck; commit, don't roll back)
- Fix #3 (n=18, on top of bge): recall 0.83 → 1.00, NDCG@5 0.63 → 0.82, MRR 0.57 → 0.76. Attribution: sparse widens the pool (recall@20 0.89 → 0.94), fusion alone drops top-5 to 0.72, the ColBERT rerank delivers the win.
- Cold open: stale gen5 chart first at baseline AND after dedup+bge+hybrid; gen6 first only with the filter.
- Demo queries: fix #1 "Tell me the Pokedex entry for Gengar" (dup rate 80% before, distinct docs after); fix #2 "the electric mouse … cheek pouches" (MiniLM returns Togedemaru, bge returns Pikachu); fix #3 Zubat echolocation query (bge misses, hybrid recovers).

## Pre-show checklist (T-60 min)

1. Fresh baseline if a rehearsal touched it: `uv run python snapshot.py restore` (seconds). Full rebuild (`ingest.py && prep.py`; prep snapshots automatically) only if the corpus or golden set changed.
2. `cat data/.retrieval_state.json` → must be `{"mode": "minilm", "current_only": false}` (ingest resets it; never trust a leftover).
3. `uv run python verify_arc.py --baseline-only` → every flaw red (fix1 dup@5 ≈ 0.67, fix2 recall ≈ 0.64, fix3 NDCG ≈ 0.22, cold open False). Non-destructive.
4. Collections: `pokemon_webinar` = 22,946 pts, `pokemon_viz` = 240 pts.
5. Start the app, let the model warm-up spinner finish, ask one throwaway question, confirm the badge reads `minilm`, then restart the app for a clean chat history.
6. Notebook: restart kernel, run ONLY the setup cell. Keep the executed backup notebook open in a second tab.
7. FI: logged in, project `pokedex-rag`, Experiments view pre-loaded. QUI: `pokemon_viz` Visualize tab pre-loaded with `{"limit": 1000}`.
8. Screen layout: App + notebook on the shared screen, FI dashboard ready to swap in; hide bookmarks bar, 125% zoom, notifications off.

## Fallbacks

- **Any notebook cell fails live** → switch to the executed backup tab, narrate from its output, debug never.
- **Cold open answers correctly** (parametric leak) → show the retrieval panel: the stale chunk still won retrieval; narrate "the generator got lucky, retrieval did not" and continue. The filter beat still lands.
- **Qdrant Cloud or Anthropic hiccup** → backup notebook carries every number; the app demo degrades to narrated screenshots (keep 3: wrong cold open, dup-crowded panel, corrected answer).
- **A score behaves oddly on FI** → Rishav narrates the local gold-label number from the notebook and moves on; reconcile in Q&A if asked.
- **Multi-hop collapses to one retrieval live** (Haiku answers the compound question in one search) → switch to the pre-captured rehearsal trace in FI and narrate from it; never re-roll the question on stage.

## Rehearsal gates (before the dry run)

- `verify_arc.py`: every fix moves its number (DESTRUCTIVE: revert with `snapshot.py restore` after; it refuses to run if the cluster has no snapshot). Update the expected numbers above with what it prints.
- Save the executed notebook copy from the successful rehearsal run as the backup.
- Multi-hop gate: the Drowzee compound question must produce two-plus retriever spans in the FI trace; bookmark that rehearsal trace as the live fallback.
- Click through `pokemon_viz` in the Visualize tab: duplicate clusters must be visible before dedup and visibly thinner after. Snorlax and Gengar carry the strongest clusters (6× each); adjust `VIZ_POKEMON` in ingest.py if not.
- Confirm the dashboard triad behavior with Rishav. Measured via the `ai-evaluation` SDK (`model="turing_flash"`, context passed as one string: a list 500s): groundedness stays **green** through every retrieval failure (a grounded "I don't know" passes), context_relevance dips 0.7 → 0.5 on a dense miss but never collapses, and chunk_utilization scores the *answer's* use of context (0.0 whenever the agent refuses), not duplication itself. Registry identifiers confirmed: `context_relevance`, `chunk_utilization`, `chunk_attribution`, `groundedness`, `factual_accuracy`, `detect_hallucination`. The open question for Rishav: how the platform's dataset runs (vs standalone SDK calls) present these, and which one anchors each beat's dashboard read.
