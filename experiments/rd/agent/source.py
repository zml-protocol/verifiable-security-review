"""Neutral, read-only two-revision source surface for RD phases A and B."""

from __future__ import annotations

import fnmatch
import posixpath
import re
from pathlib import Path

from spike.gitrepo import GitError, GitRepo
from spike.linemap import LineMap, MapStatus
from spike.session import DEFAULT_DENY, ToolInputError

REVISIONS = ("revision_A", "revision_B")
_IDENT_RE = re.compile(r"^[A-Za-z_$][\w$]*$")
_MAX_LINE_CHARS = 300
_MAX_DIFF_LINES = 400


def _clean_path(path: str) -> str:
    p = posixpath.normpath(path.strip().removeprefix("./"))
    if not path.strip() or p.startswith(("/", "..")) or "\x00" in p or p == ".":
        raise ToolInputError("bad_path", f"invalid repository-relative path: {path!r}")
    return p


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_LINE_CHARS else text[:_MAX_LINE_CHARS] + " …[truncated]"


class SourceSurface:
    def __init__(self, repo: str | Path, revisions: dict[str, str], deny_paths: list[str] | None = None):
        if set(revisions) != set(REVISIONS):
            raise ValueError("source surface requires revision_A and revision_B")
        self.repo = GitRepo(repo)
        self.commits = {rev: self.repo.resolve(ref) for rev, ref in revisions.items()}
        self.deny = tuple(p.lower() for p in (*DEFAULT_DENY, *(deny_paths or [])))
        self.linemap = LineMap(self.repo, self.commits["revision_A"], self.commits["revision_B"])

    def _revision(self, revision: str) -> str:
        if revision not in REVISIONS:
            raise ToolInputError("bad_revision", "revision must be revision_A or revision_B")
        return revision

    def allowed(self, path: str) -> bool:
        p = path.lower()
        name = posixpath.basename(p)
        return not any(fnmatch.fnmatchcase(p if "/" in pat else name, pat) for pat in self.deny)

    def text(self, revision: str, path: str) -> str | None:
        revision, path = self._revision(revision), _clean_path(path)
        if not self.allowed(path):
            raise ToolInputError("path_denied", f"{path} is not available in this review")
        data = self.repo.read_blob(self.commits[revision], path)
        if data is None:
            return None
        if b"\0" in data[:8000]:
            raise ToolInputError("binary_file", f"{path} is binary")
        return data.decode("utf-8", errors="replace")

    def lines(self, revision: str, path: str) -> list[str]:
        text = self.text(revision, path)
        if text is None:
            raise ToolInputError("not_found", f"{path} does not exist in {revision}")
        return text.splitlines()

    def list_files(self, revision: str, prefix: str = "", limit: int = 300) -> dict:
        revision = self._revision(revision)
        if not isinstance(limit, int) or not 1 <= limit <= 300:
            raise ToolInputError("bad_limit", "limit must be an integer from 1 to 300")
        prefix = prefix.strip().removeprefix("./")
        files = [p for p in self.repo.ls_files(self.commits[revision])
                 if p.startswith(prefix) and self.allowed(p)]
        return {"files": files[:limit], "total": len(files), "truncated": len(files) > limit}

    def read_code(self, revision: str, path: str, start_line: int = 1,
                  end_line: int | None = None) -> dict:
        revision, path = self._revision(revision), _clean_path(path)
        lines = self.lines(revision, path)
        if not isinstance(start_line, int) or (end_line is not None and not isinstance(end_line, int)):
            raise ToolInputError("bad_range", "line numbers must be integers")
        start = max(1, start_line)
        end = min(len(lines), end_line if end_line is not None else start + 199, start + 199)
        if start > end:
            raise ToolInputError("bad_range", f"{path} has {len(lines)} lines in {revision}")
        code = "\n".join(f"{start + i:>6} | {_clip(t)}" for i, t in enumerate(lines[start - 1:end]))
        return {"path": path, "revision": revision, "start_line": start, "end_line": end,
                "total_lines": len(lines), "code": code}

    def _grep(self, revision: str, pattern: str, path_glob: str | None, ignore_case: bool) -> dict:
        revision = self._revision(revision)
        specs = [f":(glob){_clean_path(path_glob)}"] if path_glob else []
        try:
            found = self.repo.grep(self.commits[revision], pattern, specs, ignore_case)
        except GitError as e:
            if "-e option, '" not in str(e):
                raise
            raise ToolInputError("bad_pattern", "not a valid extended regular expression") from None
        hits = [h for h in found if self.allowed(h.path)]
        return {"hits": [{"path": h.path, "line": h.line, "text": _clip(h.text)}
                         for h in hits[:50]], "total": len(hits), "truncated": len(hits) > 50}

    def search_code(self, revision: str, pattern: str, path_glob: str | None = None,
                    ignore_case: bool = False) -> dict:
        return self._grep(revision, pattern, path_glob, ignore_case)

    def find_symbol(self, revision: str, name: str, path_glob: str | None = None) -> dict:
        name = name.rsplit(".", 1)[-1]
        if not _IDENT_RE.match(name):
            raise ToolInputError("bad_symbol", "name must be an identifier")
        esc = name.replace("$", r"\$")
        pattern = (rf"(\b(def|class|func|function|fn|type|interface|struct|trait|enum)\s+"
                   rf"(\([^)]*\)\s*)?{esc}\b)|(\b{esc}\s*[:=]\s*(async\s+)?(function\b|\())")
        return self._grep(revision, pattern, path_glob, False)

    def changed_files(self) -> dict:
        files = []
        for c in self.linemap.changes:
            paths = [p for p in (c.old_path, c.new_path) if p]
            if all(self.allowed(p) for p in paths):
                files.append({"status": c.status, "revision_A_path": c.old_path,
                              "revision_B_path": c.new_path})
        return {"files": files}

    def diff_file(self, path: str) -> dict:
        path = _clean_path(path)
        change = self.linemap.change_for(path, "head") or self.linemap.change_for(path, "base")
        if change is None:
            raise ToolInputError("unchanged", f"{path} is not changed between the revisions")
        paths = list(dict.fromkeys(p for p in (change.old_path, change.new_path) if p))
        if not all(self.allowed(p) for p in paths):
            raise ToolInputError("path_denied", f"{path} is not available in this review")
        raw = self.repo.diff(self.commits["revision_A"], self.commits["revision_B"], paths).decode(
            "utf-8", errors="replace")
        rows, budget = [], _MAX_DIFF_LINES
        for line in raw.splitlines():
            # Commit/blob metadata and git's base/head names are deliberately hidden.  Hunk
            # coordinates and source rows are sufficient under neutral revision labels.
            if line.startswith("@@ ") or (line and line[0] in " +-" and
                    not line.startswith(("--- ", "+++ ")) and budget > 0):
                rows.append(_clip(line))
                if line and line[0] in " +-" and not line.startswith(("--- ", "+++ ")):
                    budget -= 1
        return {"status": change.status, "revision_A_path": change.old_path,
                "revision_B_path": change.new_path, "diff": "\n".join(rows),
                "truncated": budget <= 0}

    def map_location(self, from_revision: str, path: str, line: int) -> dict:
        revision, path = self._revision(from_revision), _clean_path(path)
        self.lines(revision, path)
        internal = "base" if revision == "revision_A" else "head"
        m = self.linemap.map(path, line, internal)
        other = "revision_B" if revision == "revision_A" else "revision_A"
        out = {"status": m.status.value, "to_revision": other}
        if m.to_path:
            out["to_path"] = m.to_path
        if m.to_line:
            out["to_line"] = m.to_line
        if m.status is MapStatus.IN_HUNK and m.hunk:
            h = m.hunk
            out["changed_lines"] = {
                "revision_A": f"{h.old_start}-{h.old_start + h.old_count - 1}" if h.old_count else None,
                "revision_B": f"{h.new_start}-{h.new_start + h.new_count - 1}" if h.new_count else None,
            }
        return out
