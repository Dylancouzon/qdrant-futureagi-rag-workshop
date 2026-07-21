# Runbook: 60 Minutes

Surfaces: **App** (Streamlit), **NB** (`workshop.ipynb`), **FI** (Future AGI), **QUI** (Qdrant Cloud Web UI). Times are ceilings.

## Run Of Show

| Time | Beat | Owner | Surface | Must land |
|---|---|---|---|---|
| 0:00-0:05 | Intro + one correct question | Dylan | App | Correct cited answer, retrieval panel visible |
| 0:05-0:10 | Cold open: "Does Steel resist Ghost and Dark?" | Dylan | App | Wrong answer; stale `typechart-steel-gen5` wins retrieval |
| 0:10-0:14 | Trace + judge calibration | Rishav | FI | Cold-open trace on screen; custom judge marks it wrong |
| 0:14-0:19 | Decay curve | Dylan | NB §1 | recall@5 falls 0.67 → 0.39 as the dex grows |
| 0:19-0:28 | Fix #1: dedup | Dylan → Rishav | NB §2 → QUI → FI | duplicate rate 0.67 → 0.00; 22.9k → 8.4k points |
| 0:28-0:35 | Fix #2: embedding migration | Dylan → Rishav | NB §3 → FI | MiniLM vs bge A/B: recall 0.64 → 1.00 |
| 0:35-0:43 | Fix #3: hybrid + rerank | Dylan → Rishav | NB §4 → App → FI | recall 0.83 → 1.00; NDCG 0.63 → 0.82 |
| 0:43-0:48 | Cold-open close: `is_current` filter | Dylan | NB §5 → App | corrected answer; metadata fixes staleness |
| 0:48-0:51 | Multi-hop trace | Rishav | NB §6 → FI | two retriever spans from one compound question |
| 0:51-0:57 | Experiments view | Rishav | FI | before/after scoreboard across the fixes |
| 0:57-1:00 | Close + Q&A buffer | both | n/a | measure → locate layer → fix → re-measure |

If running late: skip the `group_by` cell in fix #1, shorten the 0:51 recap, compress fix #2 to flip → score → commit, then skip the second Web UI look after dedup. Keep the multi-hop trace and cold-open close.

## Expected Numbers

Verified 2026-07-21 on the full-dex corpus. If a live number is wildly off, use the backup notebook output.

| Check | Expected |
|---|---|
| Decay curve | recall@5 0.67 → 0.45 → 0.39; dup-rate@5 0.44 → 0.51 → 0.52 |
| Corpus sizes | Gen 1: 1,314 pts; Gen 1-4: 8,351 pts; full: 22,946 pts |
| Fix #1 | duplicate rate 0.67 → 0.00; `pokemon_webinar` 22,946 → 8,416; `pokemon_viz` 240 → 95 |
| Fix #1 demo query (Gengar) | duplicate rate@5 0.80 → 0.00 (all five slots are `gengar-gen1-types` copies) |
| Fix #2 | n=14; MiniLM recall@5 0.64 → bge 1.00 |
| Fix #3 | n=18; recall 0.83 → 1.00; NDCG@5 0.63 → 0.82; MRR 0.57 → 0.76 |
| Fix #3 attribution | sparse widens recall@20 0.89 → 0.94; fusion-only top-5 drops to 0.72; ColBERT rerank delivers the win |
| Cold open | stale Gen 5 chart wins until the `is_current` filter; Gen 6 wins after |

Demo queries:

- Fix #1: `Tell me the Pokedex entry for Gengar`
- Fix #2: `the electric mouse Pokemon that stores electricity in the pouches on its cheeks`
- Fix #3: `A Pokemon that lives in dark caves and uses sound waves to navigate and hunt.`
- Multi-hop: `What does Drowzee eat, and is that Pokemon weak to Bug-type attacks?`

## Pre-Show Checklist

1. Restore if needed: `uv run python snapshot.py restore`. Rebuild with `ingest.py` + `prep.py` only if the corpus or golden set changed.
2. Confirm `cat data/.retrieval_state.json` prints `{"mode": "minilm", "current_only": false}` (a missing file means the same default).
3. Run `uv run python verify_arc.py --baseline-only`; expected flaws stay red.
4. Confirm collections: `pokemon_webinar` = 22,946 points, `pokemon_viz` = 240 points.
5. Start the app, let models warm, ask one throwaway question, confirm the badge reads `minilm`, then restart for clean history.
6. Restart notebook kernel and run only the setup cell. Keep the executed backup notebook open.
7. FI: logged into project `pokedex-rag`; Experiments view ready. QUI: `pokemon_viz` Visualize tab ready with `{"limit": 1000}`.
8. Screen: App + notebook on shared display; FI ready to swap in; bookmarks hidden; 125% zoom; notifications off.

## Fallbacks

- Notebook cell fails: switch to the executed backup tab and narrate from output.
- Cold open answers correctly: show that stale retrieval still won; call it a generator lucky break and continue.
- Qdrant Cloud or Anthropic hiccup: use the backup notebook numbers and the three prepared screenshots: wrong cold open, duplicate-crowded panel, corrected answer.
- FI score behaves oddly: Rishav uses the notebook's local gold-label number and reconciles later.
- Multi-hop collapses to one retrieval: use the bookmarked rehearsal trace; do not retry live.

## Rehearsal Gates

- Run `verify_arc.py` before the dry run. It is destructive; restore afterward.
- Save the successful executed notebook as the backup.
- Bookmark a rehearsal trace where the Drowzee question produces two-plus retriever spans.
- Check `pokemon_viz` in Qdrant Cloud: duplicate clusters should be visible before dedup and thinner after.
- Confirm Future AGI dashboard reads with Rishav. SDK measurements so far: `groundedness` can stay green through retrieval failures, `context_relevance` dips but does not collapse, and `chunk_utilization` measures answer use of context rather than duplication.
