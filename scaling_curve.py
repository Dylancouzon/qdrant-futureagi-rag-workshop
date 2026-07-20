"""Generate the scaling-decay curve (arc step 3): the same golden queries scored against
the ACTUAL broken pipeline (weak dense, fragmented + duplicated) as the haystack grows
500 -> 2k -> 10k. Camera never opens this; the notebook loads its output.

Honest controlled experiment: gold documents are fixed and single-copy; the collection
grows by piling on duplicated/fragmented distractors, exactly like the real ingest. Two
things decay together — recall@5 falls and the duplicate rate in the top-k rises — which
is precisely what dedup (fix #1) and hybrid+rerank (fix #3) later reverse. No embedding
model comparison here: on this corpus the model is not the lever (see fix #2), so mixing
it into the opening hook would mislead. Writes data/scaling_curve.{json,png}.

    uv run python scaling_curve.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from helpers import config, embeddings
from helpers.corpus import build_corpus
from ingest import build_points, load_gold_doc_ids

SIZES = [500, 2000, 10000]
SCALE_COLLECTION = "pokemon_scale"
DATA = Path(__file__).resolve().parent / "data"
K = config.TOP_K


def semantic_queries():
    rows = [json.loads(l) for l in (DATA / "golden_dataset.jsonl").read_text().splitlines() if l.strip()]
    return [r for r in rows if r["exercises"] in ("fix2_embedding", "fix3_hybrid", "fix1_dedup")]


def main():
    load_dotenv()
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
                          timeout=120)
    queries = semantic_queries()

    # Build the full broken point set once (fragmented flavor + duplicated distractors),
    # then embed every unique text once and reuse across sizes.
    gold_ids = load_gold_doc_ids()
    pts = build_points(build_corpus(), gold_ids, dup_factor=2)
    print(f"built {len(pts)} broken points; embedding unique texts (weak)...")
    uniq = list({p["text"] for p in pts})
    vec = dict(zip(uniq, embeddings.dense(uniq, config.MODEL_DENSE_WEAK)))
    qvec = embeddings.dense([r["query"] for r in queries], config.MODEL_DENSE_WEAK, is_query=True)

    # Gold points first (always present), then distractors/duplicates fill to each size.
    gold_pts = [p for p in pts if p["doc_id"] in gold_ids]
    rest = [p for p in pts if p["doc_id"] not in gold_ids]

    results = []
    for size in SIZES:
        pool = gold_pts + rest[: max(0, size - len(gold_pts))]
        client.delete_collection(SCALE_COLLECTION)
        client.create_collection(SCALE_COLLECTION, vectors_config={
            config.DENSE_WEAK: models.VectorParams(size=config.DIM_DENSE_WEAK, distance=models.Distance.COSINE)})
        for s in range(0, len(pool), 256):
            batch = pool[s:s + 256]
            client.upsert(SCALE_COLLECTION, points=[
                models.PointStruct(id=s + i, vector={config.DENSE_WEAK: vec[p["text"]]},
                                   payload={"doc_id": p["doc_id"], "text": p["text"]})
                for i, p in enumerate(batch)])
        hit, dup = 0, 0.0
        for r, qv in zip(queries, qvec):
            top = client.query_points(SCALE_COLLECTION, query=qv, using=config.DENSE_WEAK,
                                      limit=K, with_payload=["doc_id", "text"]).points
            docs = [(h.payload["doc_id"], h.payload["text"]) for h in top]
            hit += int(any(d[0] in set(r["gold_doc_ids"]) for d in docs))
            dup += 1 - len(set(docs)) / len(docs) if docs else 0
        results.append({"size": size, "recall": hit / len(queries), "dup_rate": dup / len(queries)})
        print(f"  size={size:>6}  recall@{K}={results[-1]['recall']:.2f}  dup_rate@{K}={results[-1]['dup_rate']:.2f}")

    client.delete_collection(SCALE_COLLECTION)
    (DATA / "scaling_curve.json").write_text(json.dumps(results, indent=2))

    xs = [r["size"] for r in results]
    fig, ax1 = plt.subplots(figsize=(7, 4.2))
    ax1.plot(xs, [r["recall"] for r in results], "o-", color="#cc0000", label="recall@5 (baseline)")
    ax1.set_ylabel("recall@5", color="#cc0000"); ax1.set_ylim(0, 1.05)
    ax2 = ax1.twinx()
    ax2.plot(xs, [r["dup_rate"] for r in results], "s--", color="#e08a00", label="duplicate rate@5")
    ax2.set_ylabel("duplicate rate@5", color="#e08a00"); ax2.set_ylim(0, 1.05)
    ax1.set_xscale("log"); ax1.set_xticks(xs); ax1.set_xticklabels([str(x) for x in xs])
    ax1.set_xlabel("collection size (points)")
    plt.title("Same golden queries, growing haystack — baseline decays")
    fig.tight_layout(); plt.savefig(DATA / "scaling_curve.png", dpi=130)
    print(f"wrote {DATA/'scaling_curve.json'} and scaling_curve.png")


if __name__ == "__main__":
    main()
