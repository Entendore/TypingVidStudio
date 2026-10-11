#!/usr/bin/env python3
"""Splits the part of studio_lib.py I haven't received yet into
~45KB chat-safe files. Run:  python split_for_chat.py"""
from pathlib import Path

src = Path("studio_lib.py")
text = src.read_text(encoding="utf-8")

# Start just after `return rows` — the last content that came through.
anchor = 'rows[ri][ci] = (dst, rows[ri][ci][1])\n    return rows'
idx = text.find(anchor)
start_at = (idx + len(anchor)) if idx != -1 else 0
text = text[start_at:]

MAX_CHARS = 45_000          # safely under the ~60K cap
part, start, n = 1, 0, len(text)
while start < n:
    end = min(start + MAX_CHARS, n)
    if end < n:                          # don't cut mid-line
        nl = text.rfind("\n", start, end)
        if nl > start:
            end = nl + 1
    out = Path(f"paste_part_{part}.txt")
    out.write_text(text[start:end], encoding="utf-8")
    print(f"{out}: {end - start:,} chars  ->  paste in message #{part}")
    start, part = end, part + 1
print(f"\nDone: {part - 1} part file(s). Send each one, in order.")