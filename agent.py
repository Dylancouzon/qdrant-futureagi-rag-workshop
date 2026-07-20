"""The agentic RAG agent, camera-visible. Qdrant retrieval + LangGraph, calls verbatim.

A LangGraph ReAct agent with one tool: Pokedex search backed by Qdrant. The agent decides
when to search, can search more than once (multi-hop), and cites its sources. A strict
grounding prompt keeps it from answering from the model's own memory. Only retrieved
documents are authoritative, because the games change across generations.

All retrieval goes through `retrieve()`. Its **mode** is what each workshop fix changes:
`minilm` (broken baseline) → `bge` (fix #2 migration) → `hybrid` (fix #3 dense+sparse+
rerank), plus a `current_only` payload filter (the cold-open close). The mode is stored in
a file so the notebook can flip it and the running Streamlit app picks it up on the next
question, and the audience returns to the chat UI and sees the agent answer better.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from qdrant_client import QdrantClient, models

from helpers import config, embeddings

try:
    from langchain.agents import create_agent  # langchain >= 1.0
except ImportError:
    from langgraph.prebuilt import create_react_agent as create_agent

load_dotenv()

# Tracing (Future AGI): registering here, not in the notebook, means every process that
# runs the agent is traced: the notebook, the Streamlit app, and the rehearsal scripts.
# traceAI auto-instruments LangGraph, so Qdrant retrieval shows up as retriever spans
# with no manual span code.
if os.getenv("FI_API_KEY"):
    from fi_instrumentation import register
    from traceai_langchain import LangChainInstrumentor

    register(project_name="pokedex-rag")
    LangChainInstrumentor().instrument()

client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"],
                      timeout=60)

GROUNDING_PROMPT = (
    "You are a Pokedex assistant. Answer ONLY using the documents returned by the "
    "search_pokedex tool. The Pokemon games change across generations, so your own "
    "memory is NOT reliable — treat the retrieved documents as the single source of "
    "truth. If the documents do not contain the answer, say you don't know. Cite the "
    "name in brackets for every fact you state, e.g. [magnemite]."
)

# Cross-process retrieval switch. The notebook flips it with set_retrieval(); the Streamlit
# app reads it per question. File-based so the two processes agree; ingest.py resets it.
# ponytail: one flag file for a single-user demo; use a real store if it ever goes multi-user.
_STATE_FILE = config.STATE_FILE


def _read_state() -> dict:
    if _STATE_FILE.exists():
        return {**config.DEFAULT_STATE, **json.loads(_STATE_FILE.read_text())}
    return dict(config.DEFAULT_STATE)


def retrieval_state() -> dict:
    """Current retrieval switch — the app shows it so the audience can track each flip."""
    return _read_state()


def set_retrieval(*, mode: str | None = None, current_only: bool | None = None) -> None:
    """Flip the agent's retrieval behavior (persisted for the app). Called by the notebook."""
    state = _read_state()
    if mode is not None:
        state["mode"] = mode
    if current_only is not None:
        state["current_only"] = current_only
    _STATE_FILE.write_text(json.dumps(state))


# The retrieval panel reads the chunks retrieved during a run. Single-user demo.
_last_retrieval: list[dict] = []


def reset_retrieval() -> None:
    _last_retrieval.clear()


def get_retrieval() -> list[dict]:
    return list(_last_retrieval)


def retrieve(query: str, *, mode: str | None = None, current_only: bool | None = None,
             limit: int = config.TOP_K) -> list[dict]:
    """Retrieve from Qdrant. `mode` selects the pipeline each workshop fix upgrades to."""
    state = _read_state()
    mode = mode or state["mode"]
    current_only = state["current_only"] if current_only is None else current_only

    # Cold-open close: keep only current documents (the payload-filter fix).
    query_filter = None
    if current_only:
        query_filter = models.Filter(must=[
            models.FieldCondition(key="is_current", match=models.MatchValue(value=True))
        ])

    if mode == "hybrid":
        # Fix #3: one multi-stage call: dense + sparse prefetch, fused RRF, ColBERT rerank.
        # The dense arm stays on MiniLM: fix #2 measured the bigger model as no better on
        # this corpus, and hybrid scores identically with either arm (verified).
        sp = embeddings.sparse([query], is_query=True)[0]
        hits = client.query_points(
            collection_name=config.COLLECTION,
            prefetch=[models.Prefetch(
                prefetch=[
                    models.Prefetch(query=embeddings.dense([query], config.MODEL_DENSE_WEAK,
                                    is_query=True)[0], using=config.DENSE_WEAK, limit=20,
                                    filter=query_filter),
                    models.Prefetch(query=models.SparseVector(indices=sp[0], values=sp[1]),
                                    using=config.SPARSE, limit=20, filter=query_filter),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF), limit=20,
            )],
            query=embeddings.colbert([query], is_query=True)[0],
            using=config.COLBERT, limit=limit, with_payload=True,
        ).points
    else:
        # Baseline / fix #2: single dense query on the small (MiniLM) or large (bge) vector.
        model = config.MODEL_DENSE_STRONG if mode == "bge" else config.MODEL_DENSE_WEAK
        using = config.DENSE_STRONG if mode == "bge" else config.DENSE_WEAK
        hits = client.query_points(
            collection_name=config.COLLECTION,
            query=embeddings.dense([query], model, is_query=True)[0],
            using=using, limit=limit, with_payload=True, query_filter=query_filter,
        ).points

    chunks = [
        {
            "rank": rank, "score": hit.score,
            "doc_id": hit.payload["doc_id"], "name": hit.payload["name"],
            "generation": hit.payload["generation"], "doc_type": hit.payload["doc_type"],
            "sprite_url": hit.payload["sprite_url"], "text": hit.payload["text"],
        }
        for rank, hit in enumerate(hits, start=1)
    ]
    _last_retrieval.extend(chunks)
    return chunks


def _format_for_model(chunks: list[dict]) -> str:
    # The generator cites by name and never sees the generation. Generation is payload
    # metadata for filtering, not an answer signal. If the model saw it in the text, doc_id,
    # or a label, it would silently disambiguate stale-vs-current documents and the
    # cold-open conflict would never surface. The human panel still shows generation badges.
    if not chunks:
        return "No documents found."
    return "\n".join(f"[{c['name']}] {c['text']}" for c in chunks)


@tool
def search_pokedex(query: str) -> str:
    """Search the Pokedex for documents relevant to the query. Returns cited chunks."""
    return _format_for_model(retrieve(query))


llm = ChatAnthropic(model=config.GENERATOR_MODEL, temperature=0)
agent = create_agent(llm, [search_pokedex], prompt=GROUNDING_PROMPT)


def ask(question: str) -> tuple[str, list[dict]]:
    """Run the agent on a question. Returns (answer, retrieved chunks for the panel)."""
    reset_retrieval()
    result = agent.invoke({"messages": [("user", question)]})
    answer = result["messages"][-1].content
    return answer, get_retrieval()


if __name__ == "__main__":
    # ponytail: smoke-check the agent answers a working query and cites a source.
    ans, chunks = ask("Which Pokemon puts its prey to sleep and then eats their dreams?")
    print("ANSWER:", ans)
    print("RETRIEVED:", [(c["rank"], c["doc_id"], round(c["score"], 3)) for c in chunks])
