"""Word-boundary chunker. Camera never opens this file.

The broken baseline over-chunks with a tiny size so flavor text and type-chart docs
fragment across several points — the fragmentation half of fix #1.
"""

from __future__ import annotations

# Tiny on purpose: fragments short flavor text into multiple points (the broken state).
BROKEN_CHUNK_CHARS = 45
BROKEN_OVERLAP_CHARS = 15


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split into <=size-char chunks on word boundaries with a char overlap."""
    words = text.split()
    if not words:
        return []
    chunks, cur, cur_len = [], [], 0
    for w in words:
        if cur and cur_len + 1 + len(w) > size:
            chunks.append(" ".join(cur))
            # start next chunk with a tail overlap
            back, blen = [], 0
            for pw in reversed(cur):
                if blen + len(pw) > overlap:
                    break
                back.insert(0, pw)
                blen += len(pw) + 1
            cur, cur_len = back, sum(len(x) + 1 for x in back)
        cur.append(w)
        cur_len += 1 + len(w)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


if __name__ == "__main__":
    # ponytail: check tiny chunking actually fragments a flavor-length string.
    s = "Drowzee: Puts enemies to sleep then eats their dreams. Occasionally gets sick."
    cs = chunk_text(s, BROKEN_CHUNK_CHARS, BROKEN_OVERLAP_CHARS)
    assert len(cs) >= 2, cs
    assert all(len(c) <= BROKEN_CHUNK_CHARS + 15 for c in cs), cs
    print(f"{len(cs)} chunks:", cs)
