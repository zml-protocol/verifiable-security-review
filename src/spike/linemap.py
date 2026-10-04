"""Deterministic cross-revision location mapping from the diff itself.

A line outside every changed hunk has an exact counterpart on the other side;
only lines inside a hunk need semantic mapping, and those are reported as such
rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from .gitrepo import FileChange, GitRepo, Hunk

Side = Literal["base", "head"]


class MapStatus(StrEnum):
    UNCHANGED_FILE = "unchanged_file"  # file identical on both sides
    TRANSLATED = "translated"  # outside every hunk; counterpart line is exact
    IN_HUNK = "in_hunk"  # line was added, removed or rewritten by the change
    FILE_ABSENT = "file_absent"  # file does not exist on the other side


@dataclass(frozen=True)
class Mapping:
    status: MapStatus
    to_path: str | None
    to_line: int | None
    hunk: Hunk | None = None


def _span(start: int, count: int) -> tuple[int, int] | None:
    return (start, start + count - 1) if count else None


def translate(hunks: list[Hunk], line: int, from_side: Side) -> tuple[int | None, Hunk | None]:
    """Map `line` across a list of zero-context hunks.

    Returns (counterpart_line, None) when the line is untouched, or
    (None, hunk) when it falls inside a changed region.
    """
    offset = 0
    for h in hunks:
        if from_side == "head":
            start, count, other_count = h.new_start, h.new_count, h.old_count
        else:
            start, count, other_count = h.old_start, h.old_count, h.new_count
        if count == 0:
            # Pure insertion/deletion on the other side: `start` is the line
            # after which it happened, so it shifts only lines beyond it.
            if line <= start:
                break
        else:
            if line < start:
                break
            if line <= start + count - 1:
                return None, h
        offset += other_count - count
    return line + offset, None


class LineMap:
    def __init__(self, repo: GitRepo, base: str, head: str):
        self.repo = repo
        self.commits = {"base": base, "head": head}
        self._changes: list[FileChange] | None = None
        self._hunks: dict[FileChange, list[Hunk]] = {}

    @property
    def changes(self) -> list[FileChange]:
        if self._changes is None:
            self._changes = self.repo.changed_files(self.commits["base"], self.commits["head"])
        return self._changes

    def change_for(self, path: str, side: Side) -> FileChange | None:
        for c in self.changes:
            if (c.new_path if side == "head" else c.old_path) == path:
                return c
        return None

    def hunks_for(self, change: FileChange) -> list[Hunk]:
        if change not in self._hunks:
            paths = [p for p in (change.old_path, change.new_path) if p]
            self._hunks[change] = self.repo.hunks(
                self.commits["base"], self.commits["head"], list(dict.fromkeys(paths))
            )
        return self._hunks[change]

    def changed_span(self, path: str, side: Side) -> list[tuple[int, int]]:
        """Line ranges on `side` that the change touched (empty for pure removals)."""
        change = self.change_for(path, side)
        if change is None:
            return []
        spans = []
        for h in self.hunks_for(change):
            s = _span(h.new_start, h.new_count) if side == "head" else _span(h.old_start, h.old_count)
            if s:
                spans.append(s)
        return spans

    def map(self, path: str, line: int, from_side: Side) -> Mapping:
        change = self.change_for(path, from_side)
        if change is None:
            return Mapping(MapStatus.UNCHANGED_FILE, path, line)
        to_path = change.old_path if from_side == "head" else change.new_path
        if to_path is None:
            return Mapping(MapStatus.FILE_ABSENT, None, None)
        to_line, hunk = translate(self.hunks_for(change), line, from_side)
        if hunk is not None:
            return Mapping(MapStatus.IN_HUNK, to_path, None, hunk)
        return Mapping(MapStatus.TRANSLATED, to_path, to_line)
