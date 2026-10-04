"""MCP stdio transport over one Session.

    SECREVIEW_SESSION=runs/.../session.json python -m spike.mcp_server
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from .models import SessionConfig
from .session import Session, ToolInputError

Revision = Literal["base", "head"]

INSTRUCTIONS = """\
Security verification workspace for ONE hypothesis over two revisions of a
repository: `base` (before the change) and `head` (after it). Call get_task
first. Every tool that returns code returns an anchor id; observations must
cite those anchors."""


class Citation(BaseModel):
    anchor_id: str = Field(description="An anchor id returned by a tool in this session.")
    quote: str | None = Field(
        default=None,
        description="Optional code text copied from inside that anchor, narrowing the "
        "citation to exactly those lines. Line numbers and diff markers are not needed.",
    )


# Code-bearing results go out as plain text: JSON-escaped code is hard to read
# and harder to quote back verbatim.


def _anchor_line(a: dict) -> str:
    return f"anchor {a['id']}  revision={a['revision']}  path={a['path']}  lines={a['lines']}"


def render_read(r: dict) -> str:
    return f"{_anchor_line(r['anchor'])}  (file has {r['total_lines']} lines)\n{r['code']}"


def render_hits(r: dict) -> str:
    head = f"{r['total']} hits" + (f" (showing first {len(r['hits'])})" if r["truncated"] else "")
    rows = [f"{h['anchor']}  {h['path']}:{h['line']}  | {h['text']}" for h in r["hits"]]
    return "\n".join([head, *rows])


def render_diff(r: dict) -> str:
    out = [f"{r['status']}  base: {r['base_path']}  head: {r['head_path']}"]
    for h in r["hunks"]:
        if "note" in h:
            out.append(h["note"])
            continue
        sides = [
            f"{side} lines {h[f'{side}_anchor']['lines']} anchor {h[f'{side}_anchor']['id']}"
            for side in ("base", "head")
            if f"{side}_anchor" in h
        ]
        out.append(f"@@ {' | '.join(sides)} @@")
        out.append(h["diff"])
    return "\n".join(out)


def build_server(session: Session) -> MCPServer:
    server = MCPServer(name="secreview", instructions=INSTRUCTIONS)

    def call(tool: str, render: Any = None, **args: Any) -> str:
        try:
            result = session.call(tool, **args)
        except ToolInputError as e:
            raise ToolError(f"[{e.code}] {e}") from None
        return render(result) if render else json.dumps(result, indent=1)

    @server.tool()
    def get_task() -> str:
        """Return the hypothesis under review, its components, starting hints and the rules. Call this first."""
        return call("get_task")

    @server.tool()
    def list_files(revision: Revision, prefix: str = "", limit: int = 300) -> str:
        """List repository files in a revision, optionally under a path prefix."""
        return call("list_files", revision=revision, prefix=prefix, limit=limit)

    @server.tool()
    def read_code(
        revision: Revision, path: str, start_line: int = 1, end_line: int | None = None
    ) -> str:
        """Read a line range of a file (max 200 lines per call). Returns numbered code and an anchor for exactly that range."""
        return call(
            "read_code",
            render_read,
            revision=revision,
            path=path,
            start_line=start_line,
            end_line=end_line,
        )

    @server.tool()
    def search_code(
        revision: Revision, pattern: str, path_glob: str | None = None, ignore_case: bool = False
    ) -> str:
        """Search a revision with an extended regex (git grep -E). path_glob limits files, e.g. '**/*.py'. Each hit carries a one-line anchor."""
        return call(
            "search_code",
            render_hits,
            revision=revision,
            pattern=pattern,
            path_glob=path_glob,
            ignore_case=ignore_case,
        )

    @server.tool()
    def find_symbol(revision: Revision, name: str, path_glob: str | None = None) -> str:
        """Heuristically find where a function/class/type named `name` is defined (regex over common languages; may miss or over-match)."""
        return call("find_symbol", render_hits, revision=revision, name=name, path_glob=path_glob)

    @server.tool()
    def changed_files() -> str:
        """List files that differ between base and head, with status A/M/D/R and the path on each side."""
        return call("changed_files")

    @server.tool()
    def diff_file(path: str) -> str:
        """Show the base→head diff of one file. Each hunk header names a base anchor (old lines) and a head anchor (new lines)."""
        return call("diff_file", render_diff, path=path)

    @server.tool()
    def map_location(from_revision: Revision, path: str, line: int) -> str:
        """Find the counterpart of a line in the other revision. Exact outside changed regions; reports in_hunk when the change touched that line."""
        return call("map_location", from_revision=from_revision, path=path, line=line)

    @server.tool()
    def submit_observation(
        revision: Revision,
        component: str,
        stance: Literal["supports", "contradicts", "unclear"],
        statement: str,
        citations: list[Citation] | None = None,
    ) -> str:
        """Record what the code in ONE revision shows about ONE hypothesis component. 'supports'/'contradicts' require citations of anchors from that same revision."""
        return call(
            "submit_observation",
            revision=revision,
            component=component,
            stance=stance,
            statement=statement,
            citations=[c.model_dump() for c in citations or []],
        )

    @server.tool()
    def submit_blind_spot(
        revision: Revision,
        description: str,
        component: str | None = None,
        citations: list[Citation] | None = None,
    ) -> str:
        """Record something you could not determine from the code (dynamic dispatch, config, framework behavior, missing files)."""
        return call(
            "submit_blind_spot",
            revision=revision,
            description=description,
            component=component,
            citations=[c.model_dump() for c in citations or []],
        )

    @server.tool()
    def finish(summary: str = "") -> str:
        """End the session. The summary is free text; it is not treated as a verdict."""
        return call("finish", summary=summary)

    return server


def main() -> None:
    config = SessionConfig.model_validate_json(Path(os.environ["SECREVIEW_SESSION"]).read_text())
    build_server(Session(config)).run("stdio")


if __name__ == "__main__":
    main()
