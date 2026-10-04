"""Anchors: runtime-minted handles for code the agent has actually been shown.

The agent never writes line numbers or hashes. Every tool that returns code
mints an anchor for exactly what it returned; an observation may only cite
anchors minted in its own session, optionally narrowed by quoting text from
inside them.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

Side = Literal["base", "head"]

# Gutter that read_code/diff_file prepend to each line, e.g. "-   17       | code".
_GUTTER_RE = re.compile(r"^[ +-]?[\s\d]*\| ?")


class CitationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Anchor(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    revision: Side
    path: str
    start_line: int
    end_line: int
    sha256: str

    def public(self) -> dict:
        return {
            "id": self.id,
            "revision": self.revision,
            "path": self.path,
            "lines": f"{self.start_line}-{self.end_line}",
        }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _norm(line: str) -> str:
    return " ".join(line.split())


def _window_matches(window: list[str], quote: list[str]) -> bool:
    # First and last quoted lines may be fragments; lines in between must be whole.
    if len(quote) == 1:
        return quote[0] in window[0]
    return quote[0] in window[0] and quote[-1] in window[-1] and window[1:-1] == quote[1:-1]


def locate(lines: list[str], quote: str) -> tuple[int, int]:
    """Find `quote` inside `lines`; return (offset, length) of the unique match."""
    raw = quote.splitlines()
    while raw and not raw[0].strip():
        raw.pop(0)
    while raw and not raw[-1].strip():
        raw.pop()
    if not raw:
        raise CitationError("quote_empty", "quote is empty")
    normalized = [_norm(line) for line in lines]
    for variant in (raw, [_GUTTER_RE.sub("", line, count=1) for line in raw]):
        q = [_norm(line) for line in variant]
        if not q[0]:
            continue
        k = len(q)
        found = [
            i for i in range(len(lines) - k + 1) if _window_matches(normalized[i : i + k], q)
        ]
        if len(found) == 1:
            return found[0], k
        if len(found) > 1:
            raise CitationError(
                "quote_ambiguous",
                f"quote matches {len(found)} places in the anchor; quote more lines to disambiguate",
            )
    raise CitationError("quote_not_found", "quote does not appear in the cited anchor")


class AnchorRegistry:
    def __init__(self) -> None:
        self._anchors: dict[str, Anchor] = {}
        self._lines: dict[str, list[str]] = {}
        self._commits: dict[str, str] = {}

    def mint(self, revision: Side, commit: str, path: str, start: int, lines: list[str]) -> Anchor:
        end = start + len(lines) - 1
        key = f"{revision}\0{commit}\0{path}\0{start}\0{end}"
        anchor = Anchor(
            id="A" + _sha(key)[:10],
            revision=revision,
            path=path,
            start_line=start,
            end_line=end,
            sha256=_sha("\n".join(lines)),
        )
        self._anchors[anchor.id] = anchor
        self._lines[anchor.id] = lines
        self._commits[anchor.id] = commit
        return anchor

    def get(self, anchor_id: str) -> Anchor:
        try:
            return self._anchors[anchor_id]
        except KeyError:
            raise CitationError(
                "unknown_anchor",
                f"anchor {anchor_id!r} was not returned by any tool in this session",
            ) from None

    def cite(self, anchor_id: str, quote: str | None = None) -> Anchor:
        anchor = self.get(anchor_id)
        if not quote:
            return anchor
        offset, length = locate(self._lines[anchor_id], quote)
        return self.mint(
            anchor.revision,
            self._commits[anchor_id],
            anchor.path,
            anchor.start_line + offset,
            self._lines[anchor_id][offset : offset + length],
        )

    def audit_records(self) -> list[dict]:
        """Everything needed to re-verify each anchor against the object store."""
        return [
            {**a.model_dump(), "commit": self._commits[a.id]} for a in self._anchors.values()
        ]


def verify(anchor: Anchor, file_lines: list[str]) -> bool:
    """Re-check an anchor against a fresh read of the file at its commit."""
    window = file_lines[anchor.start_line - 1 : anchor.end_line]
    return _sha("\n".join(window)) == anchor.sha256
