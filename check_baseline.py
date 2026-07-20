"""Rehearsal gate: does the broken baseline actually retrieve badly? Camera never opens this.

Proxy IR metrics per golden query on the weak-dense baseline — gold-doc rank, recall@5,
duplicate rate in the top-k — grouped by which flaw each query exercises. Run this after
ingest.py to confirm each planted flaw shows red before handing the collection to Rishav.
These are retrieval proxies; the scored evals run on the Future AGI platform.

    uv run python check_baseline.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from helpers import config, embeddings

GOLDEN = Path(__file__).resolve().parent / "data" / "golden_dataset.jsonl"


def main() -> None:
    load_dotenv()
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
    rows = [json.loads(l) for l in GOLDEN.read_text().splitlines() if l.strip()]

    print(f"{'exercises':14} {'gold_rank':>9} {'rec@5':>6} {'dup@5':>6}  query")
    agg: dict[str, list] = {}
    for r in rows:
        gold = set(r["gold_doc_ids"])
        vec = embeddings.dense([r["query"]], config.MODEL_DENSE_WEAK, is_query=True)[0]
        hits = client.query_points(config.COLLECTION, query=vec, using=config.DENSE_WEAK,
                                   limit=30, with_payload=["doc_id", "text"]).points
        ids = [h.payload["doc_id"] for h in hits]
        gold_rank = next((i + 1 for i, d in enumerate(ids) if d in gold), None)
        rec5 = int(any(d in gold for d in ids[: config.TOP_K]))
        # Same duplicate definition as the notebook and verify_arc: a repeated (doc_id, text).
        top5 = [(h.payload["doc_id"], h.payload["text"]) for h in hits[: config.TOP_K]]
        dup5 = 1 - len(set(top5)) / len(top5)
        agg.setdefault(r["exercises"], []).append((gold_rank, rec5, dup5))
        print(f"{r['exercises']:14} {str(gold_rank or '>30'):>9} {rec5:>6} {dup5:>6.2f}  {r['query'][:46]}")

    print("\n--- by flaw ---")
    for k, v in agg.items():
        miss = sum(1 for x in v if x[0] is None or x[0] > config.TOP_K)
        print(f"{k:14} n={len(v)} recall@5={sum(x[1] for x in v)/len(v):.2f} "
              f"dup@5={sum(x[2] for x in v)/len(v):.2f} gold_missed_top5={miss}")


if __name__ == "__main__":
    main()
