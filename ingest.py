"""Ingest the BROKEN-ON-PURPOSE baseline into Qdrant Cloud. Camera never opens this file.

Ships the day-one flaws the workshop fixes live:
  - weak embeddings   : one named dense vector from all-MiniLM-L6-v2 (384d)   -> fix #2
  - duplicates        : distractor docs re-ingested N times (overlapping crawls) -> fix #1
  - fragmentation     : tiny chunk size shreds flavor text into many points     -> fix #1
  - dense-only        : no sparse, no reranker vectors                          -> fix #3
  - no payload index  : generation is not indexed for filtering                 -> cold-open close

Gold docs (referenced by the golden set) are kept single-copy so duplicates are pure
distractors — otherwise dedup would raise Precision@K instead of lowering it.

    uv run python ingest.py                  # full broken baseline (~10k points)
    uv run python ingest.py --limit 20       # quick smoke ingest (first 20 Pokemon)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from helpers import chunking, config, embeddings
from helpers.corpus import build_corpus

GOLDEN_PATH = Path(__file__).resolve().parent / "data" / "golden_dataset.jsonl"

# Distractor docs are ingested this many times to simulate overlapping re-crawls.
BROKEN_DUP_FACTOR = 6
UPSERT_BATCH = 256

# Stale documents whose facts changed in a later generation. Heavily re-ingested to model
# outdated pages that accumulated from old crawls and were never cleaned up, so they crowd
# the current doc out of the top-k. The generation payload filter (arc step 7) removes them.
STALE_CONFLICT_DOC_IDS = {
    "typechart-steel-gen5",   # primary cold open: still lists Ghost/Dark resistances
    "magnemite-gen1-types",
    "magneton-gen1-types",
}
CONFLICT_DUP_FACTOR = 12

# Small sibling collection for the Qdrant Web UI point-cloud beat: recognizable Pokemon,
# same broken duplication, sized so the Visualize tab's sample shows the duplicate
# clusters honestly. The notebook dedups it alongside the main collection.
VIZ_POKEMON = ["pikachu", "charizard", "bulbasaur", "squirtle", "eevee"]


def load_gold_doc_ids() -> set[str]:
    ids: set[str] = set()
    for line in GOLDEN_PATH.read_text().splitlines():
        if line.strip():
            ids.update(json.loads(line)["gold_doc_ids"])
    return ids


def build_points(docs, gold_ids, dup_factor) -> list[dict]:
    """Chunk every doc; emit distractor docs dup_factor times, gold docs once."""
    points = []
    for doc in docs:
        if doc["doc_id"] in STALE_CONFLICT_DOC_IDS:
            copies = CONFLICT_DUP_FACTOR
        elif doc["doc_id"] in gold_ids:
            copies = 1
        else:
            copies = dup_factor
        # Over-chunk flavor text into tiny fragments (fix #1); keep short factual docs
        # (types/stats/type_chart) whole so the conflict evidence isn't truncated.
        if doc["doc_type"] == "flavor":
            chunks = chunking.chunk_text(
                doc["text"], chunking.BROKEN_CHUNK_CHARS, chunking.BROKEN_OVERLAP_CHARS
            )
        else:
            chunks = [doc["text"]]
        for copy in range(copies):
            for idx, chunk in enumerate(chunks):
                points.append({
                    "doc_id": doc["doc_id"],
                    "name": doc["name"],
                    "generation": doc["generation"],
                    "doc_type": doc["doc_type"],
                    "sprite_url": doc["sprite_url"],
                    "text": chunk,
                    "is_current": doc["is_current"],
                    "chunk_index": idx,
                    "copy": copy,
                })
    return points


def create_and_fill(client: QdrantClient, collection: str, points: list[dict]) -> None:
    """Recreate `collection` with the single weak dense vector and upsert `points`."""
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config={
            config.DENSE_WEAK: models.VectorParams(
                size=config.DIM_DENSE_WEAK, distance=models.Distance.COSINE
            ),
        },
    )
    for start in range(0, len(points), UPSERT_BATCH):
        batch = points[start : start + UPSERT_BATCH]
        vectors = embeddings.dense([p["text"] for p in batch], config.MODEL_DENSE_WEAK)
        client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(
                    id=start + i,
                    vector={config.DENSE_WEAK: vectors[i]},
                    payload=batch[i],
                )
                for i in range(len(batch))
            ],
        )
        print(f"  upserted {min(start + UPSERT_BATCH, len(points))}/{len(points)}", end="\r")
    print(f"\ncollection '{collection}' has {client.count(collection).count} points.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="first N Pokemon only (smoke test)")
    ap.add_argument("--dup-factor", type=int, default=BROKEN_DUP_FACTOR)
    args = ap.parse_args()

    load_dotenv()
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
                          timeout=120)

    docs = build_corpus()
    if args.limit:
        keep = {d["name"] for d in docs if d["doc_type"] == "stats"}
        keep = set(sorted(keep)[: args.limit])  # deterministic subset by name
        docs = [d for d in docs if d["name"] in keep or d["doc_type"] == "type_chart"]

    gold_ids = load_gold_doc_ids()
    points = build_points(docs, gold_ids, args.dup_factor)
    print(f"docs: {len(docs)}  ->  points: {len(points)} (dup_factor={args.dup_factor})")

    # Broken baseline: a SINGLE weak dense vector. No strong vector, no sparse, no colbert,
    # no payload index — every fix adds one of these live (the cluster is v1.18, so prep.py
    # adds the named vectors to this collection without recreating it).
    create_and_fill(client, config.COLLECTION, points)

    # The Web UI point-cloud collection: same broken duplication, a handful of Pokemon.
    viz_docs = [d for d in docs if d["name"] in VIZ_POKEMON]
    create_and_fill(client, config.VIZ_COLLECTION, build_points(viz_docs, gold_ids, args.dup_factor))

    # Reset the agent's retrieval switch to the broken baseline. Without this, a rehearsal
    # that ended in hybrid+filter mode would silently make the cold open answer correctly.
    config.STATE_FILE.write_text(json.dumps(config.DEFAULT_STATE))
    print(f"retrieval state reset: {config.DEFAULT_STATE}")


if __name__ == "__main__":
    main()
