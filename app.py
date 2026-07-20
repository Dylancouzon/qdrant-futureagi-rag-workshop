"""Pokedex chat UI — the audience-facing surface where the failure is experienced.

Left: chat with the agent. Right: the retrieval panel showing exactly which chunks
Qdrant returned for the last question — sprite, doc_id, generation, rank, similarity.
The panel exposes each failure before any eval confirms it. Eval scores never appear
here; they live on the Future AGI dashboard.

    uv run streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from agent import ask, retrieval_state
from helpers import ui


@st.cache_resource
def _warm_models() -> bool:
    from helpers import embeddings

    embeddings.warmup()  # pay all model-load latency at boot, never on a live question
    return True


st.set_page_config(page_title="Pokedex RAG", page_icon="🔴", layout="wide")
st.markdown(ui.POKEDEX_CSS, unsafe_allow_html=True)
st.markdown('<div class="pokedex-title">🔴 POKéDEX <span>Agentic RAG</span></div>',
            unsafe_allow_html=True)

with st.spinner("Loading embedding models…"):
    _warm_models()

if "history" not in st.session_state:
    st.session_state.history = []  # list of {question, answer, chunks}

chat_col, panel_col = st.columns([3, 2], gap="large")

with chat_col:
    for turn in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(turn["question"])
        with st.chat_message("assistant"):
            st.markdown(turn["answer"])

    question = st.chat_input("Ask the Pokedex…")
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"), st.spinner("Searching the Pokedex…"):
            answer, chunks = ask(question)
            st.markdown(answer)
        st.session_state.history.append(
            {"question": question, "answer": answer, "chunks": chunks}
        )

with panel_col:
    st.markdown(
        f'<div class="panel-head">🔍 Retrieved chunks {ui.mode_badge_html(retrieval_state())}</div>',
        unsafe_allow_html=True,
    )
    last = st.session_state.history[-1] if st.session_state.history else None
    chunks = last["chunks"] if last else []
    st.markdown(ui.retrieval_panel_html(chunks), unsafe_allow_html=True)
