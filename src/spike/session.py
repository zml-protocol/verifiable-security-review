"""One verification session: one hypothesis, one base/head pair, one agent run.

Tool implementations are transport-agnostic; `call()` is the single entry
point so every request, result and rejection lands in the transcript.
"""

from __future__ import annotations

import fnmatch
import json
import posixpath
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .anchors import AnchorRegistry, CitationError
from .gitrepo import GitError, GitRepo
from .linemap import LineMap, MapStatus
from .models import BlindSpot, Observation, SessionConfig, Side

# Files that tend to name the vulnerability outright (advisories, release notes).
DEFAULT_DENY = (
    "changelog*", "changes", "changes.*", "history.*", "news.*", "release-notes*",
    "release_notes*", "releasenotes*", "security.md", "security.rst", "security.txt",
    ".github/*", ".gitlab/*", "*.orig", "*.rej",
)  # fmt: skip

_SIDES: tuple[Side, ...] = ("base", "head")
_IDENT_RE = re.compile(r"^[A-Za-z_$][\w$]*$")
_MAX_LINE_CHARS = 300
_MAX_DIFF_LINES = 400

RULES = """\
- Investigate BOTH revisions. The hypothesis may hold on either, both, or neither.
  Contradicting evidence is exactly as valuable as supporting evidence.
- Every observation is about one revision and one component, and must cite
  anchors returned by tools for THAT revision. Use `quote` to narrow a
  citation to the lines that matter (copy code text, no line numbers needed).
- Record what you could not check (dynamic dispatch, config, framework magic)
  with submit_blind_spot instead of guessing.
- Do not state an overall verdict; the runtime derives it from observations.
- Call finish when done."""


class ToolInputError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _clean_path(path: str) -> str:
    p = posixpath.normpath(path.strip().removeprefix("./"))
    if not path.strip() or p.startswith(("/", "..")) or "\0" in p or p == ".":
        raise ToolInputError("bad_path", f"invalid repository-relative path: {path!r}")
    return p


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_LINE_CHARS else text[:_MAX_LINE_CHARS] + " …[truncated]"


class Session:
    def __init__(self, config: SessionConfig):
        self.config = config
        self.hypothesis = config.hypothesis
        self.repo = GitRepo(config.repo)
        self.commits: dict[Side, str] = {
            side: self.repo.resolve(config.revisions[side]) for side in _SIDES
        }
        self.deny = tuple(p.lower() for p in (*DEFAULT_DENY, *config.deny_paths))
        self.anchors = AnchorRegistry()
        self.linemap = LineMap(self.repo, self.commits["base"], self.commits["head"])
        self.observations: list[Observation] = []
        self.blind_spots: list[BlindSpot] = []
        self.finished = False
        self.summary: str | None = None
        self._seq = 0
        self.out_dir = Path(config.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, Callable[..., Any]] = {
            name: getattr(self, f"tool_{name}")
            for name in (
                "get_task", "list_files", "read_code", "search_code", "find_symbol",
                "changed_files", "diff_file", "map_location",
                "submit_observation", "submit_blind_spot", "finish",
            )
        }  # fmt: skip
        self._save_state()

    # ---- dispatch & ledger -------------------------------------------------

    def call(self, tool: str, **args: Any) -> Any:
        self._seq += 1
        entry: dict[str, Any] = {"seq": self._seq, "ts": time.time(), "tool": tool, "args": args}
        try:
            if tool not in self._tools:
                raise ToolInputError("unknown_tool", f"no such tool: {tool}")
            if self.finished and tool != "get_task":
                raise ToolInputError("session_finished", "session already finished")
            result = self._tools[tool](**args)
            entry["result"] = result
            return result
        except CitationError as e:
            entry["error"] = {"code": e.code, "message": str(e)}
            raise ToolInputError(e.code, str(e)) from None
        except ToolInputError as e:
            entry["error"] = {"code": e.code, "message": str(e)}
            raise
        except GitError:
            # Never leak absolute paths or SHAs through git's stderr.
            entry["error"] = {"code": "git_error", "message": "repository read failed"}
            raise ToolInputError("git_error", "repository read failed") from None
        except Exception as e:
            entry["error"] = {"code": "internal_error", "message": repr(e)}
            raise
        finally:
            with (self.out_dir / "transcript.jsonl").open("a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            self._save_state()

    def _save_state(self) -> None:
        state = {
            "session_id": self.config.session_id,
            "hypothesis_id": self.hypothesis.id,
            "commits": self.commits,
            "finished": self.finished,
            "summary": self.summary,
            "observations": [o.model_dump() for o in self.observations],
            "blind_spots": [b.model_dump() for b in self.blind_spots],
            "anchors": self.anchors.audit_records(),
        }
        (self.out_dir / "state.json").write_text(json.dumps(state, indent=2))

    # ---- helpers -----------------------------------------------------------

    def _side(self, revision: str) -> Side:
        if revision not in _SIDES:
            raise ToolInputError("bad_revision", "revision must be 'base' or 'head'")
        return revision  # type: ignore[return-value]

    def _allowed(self, path: str) -> bool:
        p = path.lower()
        name = posixpath.basename(p)
        return not any(fnmatch.fnmatchcase(p if "/" in pat else name, pat) for pat in self.deny)

    def _lines(self, side: Side, path: str) -> list[str]:
        path = _clean_path(path)
        if not self._allowed(path):
            raise ToolInputError("path_denied", f"{path} is not available in this review")
        data = self.repo.read_blob(self.commits[side], path)
        if data is None:
            raise ToolInputError("not_found", f"{path} does not exist in revision {side}")
        if b"\0" in data[:8000]:
            raise ToolInputError("binary_file", f"{path} is binary")
        return data.decode("utf-8", errors="replace").splitlines()

    def _component(self, component: str | None, required: bool) -> str | None:
        ids = [c.id for c in self.hypothesis.components]
        if component is None and not required:
            return None
        if component not in ids:
            raise ToolInputError("bad_component", f"component must be one of {ids}")
        return component

    def _citations(self, side: Side, citations: list[dict] | None) -> list:
        resolved = []
        for c in citations or []:
            if not isinstance(c, dict) or "anchor_id" not in c:
                raise ToolInputError("bad_citation", "each citation needs an anchor_id")
            anchor = self.anchors.cite(c["anchor_id"], c.get("quote"))
            if anchor.revision != side:
                raise ToolInputError(
                    "revision_mismatch",
                    f"anchor {c['anchor_id']} shows {anchor.revision} code but this "
                    f"observation is about {side}",
                )
            resolved.append(anchor)
        return resolved

    # ---- read tools --------------------------------------------------------

    def tool_get_task(self) -> dict:
        h = self.hypothesis
        return {
            "hypothesis": {
                "id": h.id,
                "property_kind": h.property_kind,
                "claim": h.claim,
                "components": [c.model_dump() for c in h.components],
                "hints": [x.model_dump(exclude_none=True) for x in h.hints],
            },
            "revisions": {
                "base": "the code before the change under review",
                "head": "the code after the change under review",
            },
            "rules": RULES,
        }

    def tool_list_files(self, revision: str, prefix: str = "", limit: int = 300) -> dict:
        side = self._side(revision)
        prefix = prefix.strip().removeprefix("./")
        files = [
            p for p in self.repo.ls_files(self.commits[side])
            if p.startswith(prefix) and self._allowed(p)
        ]  # fmt: skip
        return {"files": files[:limit], "total": len(files), "truncated": len(files) > limit}

    def tool_read_code(
        self, revision: str, path: str, start_line: int = 1, end_line: int | None = None
    ) -> dict:
        side = self._side(revision)
        path = _clean_path(path)
        lines = self._lines(side, path)
        start = max(1, start_line)
        end = min(len(lines), end_line or start + self.config.max_read_lines - 1)
        end = min(end, start + self.config.max_read_lines - 1)
        if start > end:
            raise ToolInputError("bad_range", f"{path} has {len(lines)} lines in {side}")
        window = lines[start - 1 : end]
        anchor = self.anchors.mint(side, self.commits[side], path, start, window)
        code = "\n".join(f"{start + i:>6} | {_clip(t)}" for i, t in enumerate(window))
        return {"anchor": anchor.public(), "total_lines": len(lines), "code": code}

    def _grep(self, side: Side, pattern: str, path_glob: str | None, ignore_case: bool) -> dict:
        specs = [f":(glob){_clean_path(path_glob)}"] if path_glob else []
        try:
            found = self.repo.grep(self.commits[side], pattern, specs, ignore_case)
        except GitError as e:
            # git grep rejects a malformed pattern with "fatal: -e option, '<pat>': <reason>".
            # That is the caller's input error, not a repository failure.
            if "-e option, '" not in str(e):
                raise
            reason = str(e).rsplit("': ", 1)[-1]
            raise ToolInputError(
                "bad_pattern", f"not a valid extended regular expression (git grep -E): {reason}"
            ) from None
        hits = [h for h in found if self._allowed(h.path)]
        limit = self.config.max_search_hits
        out = []
        for h in hits[:limit]:
            anchor = self.anchors.mint(side, self.commits[side], h.path, h.line, [h.text])
            out.append({"anchor": anchor.id, "path": h.path, "line": h.line, "text": _clip(h.text)})
        return {"hits": out, "total": len(hits), "truncated": len(hits) > limit}

    def tool_search_code(
        self, revision: str, pattern: str, path_glob: str | None = None, ignore_case: bool = False
    ) -> dict:
        return self._grep(self._side(revision), pattern, path_glob, ignore_case)

    def tool_find_symbol(self, revision: str, name: str, path_glob: str | None = None) -> dict:
        name = name.rsplit(".", 1)[-1]
        if not _IDENT_RE.match(name):
            raise ToolInputError("bad_symbol", "name must be an identifier")
        esc = name.replace("$", r"\$")
        pattern = (
            rf"(\b(def|class|func|function|fn|type|interface|struct|trait|enum)\s+"
            rf"(\([^)]*\)\s*)?{esc}\b)|(\b{esc}\s*[:=]\s*(async\s+)?(function\b|\())"
        )
        return self._grep(self._side(revision), pattern, path_glob, False)

    # ---- change tools ------------------------------------------------------

    def tool_changed_files(self) -> dict:
        files = []
        for c in self.linemap.changes:
            paths = [p for p in (c.old_path, c.new_path) if p]
            if all(self._allowed(p) for p in paths):
                files.append({"status": c.status, "base_path": c.old_path, "head_path": c.new_path})
        return {"files": files}

    def tool_diff_file(self, path: str) -> dict:
        path = _clean_path(path)
        change = self.linemap.change_for(path, "head") or self.linemap.change_for(path, "base")
        if change is None:
            raise ToolInputError("unchanged", f"{path} is not changed between base and head")
        paths = list(dict.fromkeys(p for p in (change.old_path, change.new_path) if p))
        if not all(self._allowed(p) for p in paths):
            raise ToolInputError("path_denied", f"{path} is not available in this review")
        raw = self.repo.diff(self.commits["base"], self.commits["head"], paths).decode(
            "utf-8", errors="replace"
        )
        return {
            "status": change.status,
            "base_path": change.old_path,
            "head_path": change.new_path,
            "hunks": self._render_hunks(raw, change.old_path, change.new_path),
        }

    def _render_hunks(self, raw: str, base_path: str | None, head_path: str | None) -> list[dict]:
        hunks: list[dict] = []
        cur: dict | None = None
        budget = _MAX_DIFF_LINES
        for line in raw.splitlines():
            m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                cur = {"o": int(m[1]), "n": int(m[2]), "rows": [], "base": [], "head": []}
                cur["o0"], cur["n0"] = cur["o"], cur["n"]
                hunks.append(cur)
                continue
            if cur is None or not line or line[0] not in " +-":
                continue
            tag, text = line[0], line[1:]
            if tag in " -":
                cur["base"].append(text)
            if tag in " +":
                cur["head"].append(text)
            o = f"{cur['o']:>5}" if tag in " -" else " " * 5
            n = f"{cur['n']:>5}" if tag in " +" else " " * 5
            if budget > 0:
                cur["rows"].append(f"{tag}{o} {n} | {_clip(text)}")
                budget -= 1
            if tag in " -":
                cur["o"] += 1
            if tag in " +":
                cur["n"] += 1
        out = []
        for h in hunks:
            entry: dict[str, Any] = {"diff": "\n".join(h["rows"])}
            for side, path, start, key in (
                ("base", base_path, h["o0"], "base"),
                ("head", head_path, h["n0"], "head"),
            ):
                if path and h[key]:
                    a = self.anchors.mint(side, self.commits[side], path, start, h[key])
                    entry[f"{side}_anchor"] = a.public()
            out.append(entry)
        if budget <= 0:
            out.append({"note": "diff truncated; use read_code for the rest"})
        return out

    def tool_map_location(self, from_revision: str, path: str, line: int) -> dict:
        side = self._side(from_revision)
        path = _clean_path(path)
        self._lines(side, path)  # existence + policy check
        m = self.linemap.map(path, line, side)
        other = "head" if side == "base" else "base"
        result: dict[str, Any] = {"status": m.status.value, "to_revision": other}
        if m.to_path:
            result["to_path"] = m.to_path
        if m.to_line:
            result["to_line"] = m.to_line
        if m.status is MapStatus.IN_HUNK and m.hunk:
            h = m.hunk
            result["changed_lines"] = {
                "base": f"{h.old_start}-{h.old_start + h.old_count - 1}" if h.old_count else None,
                "head": f"{h.new_start}-{h.new_start + h.new_count - 1}" if h.new_count else None,
            }
            result["advice"] = "this line was modified by the change; inspect diff_file"
        return result

    # ---- submission tools --------------------------------------------------

    def tool_submit_observation(
        self,
        revision: str,
        component: str,
        stance: str,
        statement: str,
        citations: list[dict] | None = None,
    ) -> dict:
        side = self._side(revision)
        comp = self._component(component, required=True)
        if stance not in ("supports", "contradicts", "unclear"):
            raise ToolInputError("bad_stance", "stance must be supports, contradicts or unclear")
        if stance != "unclear" and not citations:
            raise ToolInputError("missing_citation", f"a '{stance}' observation needs citations")
        obs = Observation(
            id=f"O{len(self.observations) + 1}",
            seq=self._seq,
            revision=side,
            component=comp,
            stance=stance,  # type: ignore[arg-type]
            statement=statement,
            citations=self._citations(side, citations),
        )
        self.observations.append(obs)
        return {"id": obs.id, "citations": [a.public() for a in obs.citations]}

    def tool_submit_blind_spot(
        self,
        revision: str,
        description: str,
        component: str | None = None,
        citations: list[dict] | None = None,
    ) -> dict:
        side = self._side(revision)
        spot = BlindSpot(
            id=f"B{len(self.blind_spots) + 1}",
            seq=self._seq,
            revision=side,
            component=self._component(component, required=False),
            description=description,
            citations=self._citations(side, citations),
        )
        self.blind_spots.append(spot)
        return {"id": spot.id}

    def tool_finish(self, summary: str = "") -> dict:
        self.finished = True
        self.summary = summary
        return {
            "observations": len(self.observations),
            "blind_spots": len(self.blind_spots),
        }
