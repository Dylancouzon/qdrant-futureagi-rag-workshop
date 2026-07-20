"""Streamlit UI plumbing — theme + retrieval-panel rendering. Camera never opens this file.

Pokedex-themed: light, high contrast, large type, readable from across a room. The
retrieval panel makes each failure visible BEFORE any score — duplicates repeating a
doc_id, a stale generation badge on the winning chunk, the right chunk ranked low.
Hard rule: no eval scores here, ever. Similarity score is a retrieval signal, not a judgment.
"""

from __future__ import annotations

import html

POKEDEX_CSS = """
<style>
  .stApp { background: #f5f6f8; }
  h1, h2, h3, p, span, div, label { color: #1a1a2e !important; }
  .pokedex-title {
    background: #cc0000; color: #ffffff !important; padding: 14px 22px;
    border-radius: 12px; font-weight: 800; font-size: 30px; letter-spacing: .5px;
    border: 4px solid #7a0000; box-shadow: 0 4px 0 #7a0000; margin-bottom: 6px;
  }
  .pokedex-title span { color: #ffde00 !important; }
  .panel-head { font-size: 20px; font-weight: 800; margin: 6px 0 10px; }
  .chunk-card {
    background: #ffffff; border: 3px solid #2a3a5e; border-radius: 12px;
    padding: 10px 12px; margin-bottom: 10px; display: grid;
    grid-template-columns: 64px 1fr; gap: 10px; align-items: center;
  }
  .chunk-card.dup { border-color: #e08a00; background: #fff8ec; }
  .sprite { width: 64px; height: 64px; image-rendering: pixelated; }
  .chunk-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 4px; }
  .rank-badge { background: #2a3a5e; color: #fff !important; font-weight: 800;
    border-radius: 6px; padding: 1px 8px; font-size: 14px; }
  .name-badge { font-weight: 800; font-size: 17px; text-transform: capitalize; }
  .gen-badge { background: #3b6ea5; color: #fff !important; border-radius: 6px;
    padding: 1px 8px; font-size: 13px; font-weight: 700; }
  .type-badge { background: #eef1f6; border: 1px solid #c7d0e0; border-radius: 6px;
    padding: 1px 8px; font-size: 13px; }
  .dup-badge { background: #e08a00; color: #fff !important; border-radius: 6px;
    padding: 1px 8px; font-size: 13px; font-weight: 700; }
  .mode-badge { background: #1a1a2e; color: #ffde00 !important; border-radius: 6px;
    padding: 2px 10px; font-size: 14px; font-weight: 700; font-family: ui-monospace, monospace;
    vertical-align: middle; margin-left: 8px; }
  .docid { font-family: ui-monospace, monospace; font-size: 13px; color: #55607a !important; }
  .chunk-text { font-size: 15px; margin: 3px 0 5px; }
  .score-row { display: flex; align-items: center; gap: 8px; }
  .score-track { flex: 1; height: 10px; background: #e6e9f0; border-radius: 5px; overflow: hidden; }
  .score-fill { height: 100%; background: #30a14e; }
  .score-num { font-variant-numeric: tabular-nums; font-size: 13px; font-weight: 700; }
</style>
"""


def _card(chunk: dict, is_dup: bool) -> str:
    dup_cls = " dup" if is_dup else ""
    dup_badge = '<span class="dup-badge">🔁 duplicate</span>' if is_dup else ""
    sprite = chunk["sprite_url"] or ""
    img = f'<img class="sprite" src="{html.escape(sprite)}"/>' if sprite else '<div class="sprite"></div>'
    pct = max(2, min(100, round(chunk["score"] * 100)))
    return f"""
    <div class="chunk-card{dup_cls}">
      {img}
      <div>
        <div class="chunk-meta">
          <span class="rank-badge">#{chunk['rank']}</span>
          <span class="name-badge">{html.escape(chunk['name'])}</span>
          <span class="gen-badge">Gen {chunk['generation']}</span>
          <span class="type-badge">{html.escape(chunk['doc_type'])}</span>
          {dup_badge}
        </div>
        <div class="docid">{html.escape(chunk['doc_id'])}</div>
        <div class="chunk-text">{html.escape(chunk['text'])}</div>
        <div class="score-row">
          <div class="score-track"><div class="score-fill" style="width:{pct}%"></div></div>
          <span class="score-num">{chunk['score']:.3f}</span>
        </div>
      </div>
    </div>
    """


def mode_badge_html(state: dict) -> str:
    """Retrieval-mode badge for the panel header — state, never a judgment."""
    label = state["mode"] + (" · current-only" if state.get("current_only") else "")
    return f'<span class="mode-badge">{html.escape(label)}</span>'


def retrieval_panel_html(chunks: list[dict]) -> str:
    """Render retrieved chunks as cards, flagging repeated doc_ids as duplicates."""
    if not chunks:
        return '<div class="chunk-text">No documents retrieved.</div>'
    seen: set[str] = set()
    cards = []
    for c in chunks:
        is_dup = c["doc_id"] in seen
        seen.add(c["doc_id"])
        cards.append(_card(c, is_dup))
    return "".join(cards)
