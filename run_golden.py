"""Run the golden set through the traced agent — the Future AGI eval entry point.

Every question goes through agent.ask(), so each run exports full traces (agent,
retriever, and LLM spans) to the `pokedex-rag` project. Run it once per arc stage —
baseline, after dedup, after the bge flip, after hybrid, after the filter — and the
platform scores the traces; the Experiments view compares the runs. The retrieval
state is whatever the notebook last set; this script never changes it.

Also writes data/golden_run-{mode}.jsonl (query, expected_answer, answer, retrieved
doc_ids, and retrieved_context — the exact text the model read, as one string, ready
for fi.evals.evaluate(context=...)). Full set takes a few minutes.

    uv run python run_golden.py                        # all 37 queries
    uv run python run_golden.py --group fix2_embedding # one slice
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import agent
from helpers import config

DATA = Path(__file__).resolve().parent / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", help="only one slice, e.g. fix2_embedding")
    args = ap.parse_args()

    rows = [json.loads(l) for l in (DATA / "golden_dataset.jsonl").read_text().splitlines()
            if l.strip()]
    if args.group:
        rows = [r for r in rows if r["exercises"] == args.group]

    state = agent.retrieval_state()
    label = state["mode"] + ("-current" if state["current_only"] else "")
    out = DATA / f"golden_run-{label}.jsonl"
    with out.open("w") as f:
        for i, r in enumerate(rows, 1):
            answer, chunks = agent.ask(r["query"])
            f.write(json.dumps({
                "query": r["query"], "exercises": r["exercises"],
                "expected_answer": r["expected_answer"], "answer": answer,
                "retrieved_doc_ids": [c["doc_id"] for c in chunks],
                # exactly what the model read, as the one context string FI evals expect
                "retrieved_context": agent._format_for_model(chunks[: config.TOP_K]),
            }) + "\n")
            print(f"[{i}/{len(rows)}] {r['query'][:60]}")
    print(f"wrote {out.name}; traces exported to Future AGI project pokedex-rag")


if __name__ == "__main__":
    main()
