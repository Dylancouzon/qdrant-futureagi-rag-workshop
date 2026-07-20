"""Pre-session prep. Camera never opens this file. Run OFFLINE before the workshop.

Adds the named vectors each fix flips to and backfills them, so the only live action on
stage is a one-line change (flip the retrieval mode) — the slow encode never runs on
camera. On v1.18+ the vectors are ADDED to the live collection with create_vector_name
(no recreate, no downtime); this is the exact migration the notebook shows.

  dense_strong : bge-large-en-v1.5 (1024d)      -> fix #2 target
  sparse       : miniCOIL                        -> fix #3 hybrid prefetch
  colbert      : colbertv2.0 MAX_SIM multivector -> fix #3 rerank

    uv run python prep.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from helpers import config, embeddings

# Small batches: ColBERT multivectors make update_vectors requests large enough to hit
# the Cloud write timeout at 128. 32 keeps each write comfortably under it.
SCROLL_BATCH = 32


def add_named_vectors(client: QdrantClient) -> None:
    """Add the fix vectors to the live collection (v1.18+, zero downtime)."""
    params = client.get_collection(config.COLLECTION).config.params
    existing = params.vectors or {}
    existing_sparse = params.sparse_vectors or {}
    if config.DENSE_STRONG not in existing:
        client.create_vector_name(
            config.COLLECTION, config.DENSE_STRONG,
            vector_name_config=models.DenseVectorNameConfig(
                dense=models.DenseVectorConfig(
                    size=config.DIM_DENSE_STRONG, distance=models.Distance.COSINE)),
        )
    if config.COLBERT not in existing:
        client.create_vector_name(
            config.COLLECTION, config.COLBERT,
            vector_name_config=models.DenseVectorNameConfig(
                dense=models.DenseVectorConfig(
                    size=config.DIM_COLBERT, distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM))),
        )
    if config.SPARSE not in existing_sparse:
        client.create_vector_name(
            config.COLLECTION, config.SPARSE,
            vector_name_config=models.SparseVectorNameConfig(sparse=models.SparseVectorConfig()),
        )


def backfill(client: QdrantClient) -> None:
    """Encode every point's text with the three models and upsert the new vectors."""
    offset = None
    done = 0
    while True:
        points, offset = client.scroll(
            collection_name=config.COLLECTION,
            limit=SCROLL_BATCH,
            offset=offset,
            with_payload=["text"],
            with_vectors=False,
        )
        if not points:
            break
        texts = [p.payload["text"] for p in points]
        strong = embeddings.dense(texts, config.MODEL_DENSE_STRONG)
        sparse = embeddings.sparse(texts)
        colbert = embeddings.colbert(texts)
        # update_vectors adds the named vectors WITHOUT touching payload. Using upsert here
        # would overwrite each point's payload with nothing — the migration gotcha.
        client.update_vectors(
            collection_name=config.COLLECTION,
            points=[
                models.PointVectors(
                    id=p.id,
                    vector={
                        config.DENSE_STRONG: strong[i],
                        config.SPARSE: models.SparseVector(
                            indices=sparse[i][0], values=sparse[i][1]
                        ),
                        config.COLBERT: colbert[i],
                    },
                )
                for i, p in enumerate(points)
            ],
        )
        done += len(points)
        print(f"  backfilled {done}", end="\r")
        if offset is None:
            break
    print(f"\nbackfill done: {done} points.")


def main() -> None:
    load_dotenv()
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
                          timeout=120)
    add_named_vectors(client)
    print("added named vectors:", config.DENSE_STRONG, config.COLBERT, config.SPARSE)
    backfill(client)


if __name__ == "__main__":
    main()
