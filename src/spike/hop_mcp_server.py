"""MCP stdio transport over one HopSession (PREREGISTRATION.md §11).

    SECREVIEW_SESSION=runs/.../session.json python -m spike.hop_mcp_server
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from .hop_session import HopConfig, HopSession
from .mcp_server import render_diff, render_hits, render_read
from .session import ToolInputError

Revision = Literal["base", "head"]

INSTRUCTIONS = """\
Evidence-path workspace for ONE hypothesis over two revisions of a repository: `base`
(before the change) and `head` (after it). Call get_task first. Hops name code by file,
line span and a copied expression."""


class Endpoint(BaseModel):
    file: str = Field(description="Repository-relative path.")
    start_line: int
    end_line: int
    expression: str = Field(description="Code text copied from those lines; the endpoint is "
                            "where this text starts. It must occur exactly once in the span.")


class Hop(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    revision: Revision
    relation: str = Field(description="A relation id from get_task, or 'unsupported'.")
    from_: Endpoint = Field(alias="from")
    to: Endpoint


def _plain(hop: Hop) -> dict:
    return hop.model_dump(by_alias=True)


def build_server(session: HopSession) -> MCPServer:
    server = MCPServer(name="secreview", instructions=INSTRUCTIONS)

    def call(tool: str, render: Any = None, **args: Any) -> str:
        try:
            result = session.call(tool, **args)
        except ToolInputError as e:
            raise ToolError(f"[{e.code}] {e}") from None
        return render(result) if render else json.dumps(result, indent=1)

    @server.tool()
    def get_task() -> str:
        """Return the hypothesis, its hints, the hop format, the relations and the rules. Call this first."""
        task = session.call("get_task")
        out = [json.dumps({k: v for k, v in task.items()
                           if k not in ("hop_format", "rules", "initial_hops",
                                        "verification_contract")}, indent=1),
               "hop_format:\n" + task["hop_format"], "rules:\n" + task["rules"]]
        if "verification_contract" in task:
            out.append("verification_contract:\n" + task["verification_contract"])
        if "initial_hops" in task:
            out.append("initial_hops (locked):\n" + task["initial_hops"])
        return "\n\n".join(out)

    @server.tool()
    def list_files(revision: Revision, prefix: str = "", limit: int = 300) -> str:
        """List repository files in a revision, optionally under a path prefix."""
        return call("list_files", revision=revision, prefix=prefix, limit=limit)

    @server.tool()
    def read_code(
        revision: Revision, path: str, start_line: int = 1, end_line: int | None = None
    ) -> str:
        """Read a line range of a file (max 200 lines per call), numbered."""
        return call("read_code", render_read, revision=revision, path=path,
                    start_line=start_line, end_line=end_line)

    @server.tool()
    def search_code(
        revision: Revision, pattern: str, path_glob: str | None = None, ignore_case: bool = False
    ) -> str:
        """Search a revision with an extended regex (git grep -E). path_glob limits files, e.g. '**/*.py'."""
        return call("search_code", render_hits, revision=revision, pattern=pattern,
                    path_glob=path_glob, ignore_case=ignore_case)

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
        """Show the base→head diff of one file."""
        return call("diff_file", render_diff, path=path)

    @server.tool()
    def map_location(from_revision: Revision, path: str, line: int) -> str:
        """Find the counterpart of a line in the other revision. Exact outside changed regions; reports in_hunk when the change touched that line."""
        return call("map_location", from_revision=from_revision, path=path, line=line)

    @server.tool()
    def validate_hop(hop: Hop) -> str:
        """Check one hop's format, that its expressions are found, and that each endpoint names the kind of code its relation requires. It does not judge whether the link itself holds."""
        return call("validate_hop", hop=_plain(hop))

    @server.tool()
    def submit_hops(hops: list[Hop]) -> str:
        """Submit your complete set of hops for the current phase, once. Every hop must pass validate_hop; duplicates are dropped; at most the stated number of distinct hops. Success locks them."""
        result = call("submit_hops", hops=[_plain(h) for h in hops])
        return result

    return server


def main() -> None:
    config = HopConfig.model_validate_json(Path(os.environ["SECREVIEW_SESSION"]).read_text())
    build_server(HopSession(config)).run("stdio")


if __name__ == "__main__":
    main()
