"""Phase-scoped MCP transport for the RD agent runtime."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

from session import RDConfig, RDSession  # noqa: E402
from spike.session import ToolInputError  # noqa: E402

Revision = Literal["revision_A", "revision_B"]


class Endpoint(BaseModel):
    file: str
    start_line: int
    end_line: int
    expression: str


class Hop(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    revision: Revision
    relation: str
    from_: Endpoint = Field(alias="from")
    to: Endpoint


def _hop(value: Hop) -> dict:
    return value.model_dump(by_alias=True)


def build_server(session: RDSession) -> MCPServer:
    server = MCPServer(name="secreview", instructions=f"RD protocol phase {session.phase.upper()}; call get_task first.")

    def call(name: str, **args: Any) -> str:
        try:
            return json.dumps(session.call(name, **args), indent=1, ensure_ascii=False)
        except ToolInputError as e:
            raise ToolError(f"[{e.code}] {e}") from None

    @server.tool()
    def get_task() -> str:
        """Return the neutral claim, this phase's immutable inputs, rules and schema vocabulary."""
        return call("get_task")

    if session.phase in ("a", "b"):
        @server.tool()
        def list_files(revision: Revision, prefix: str = "", limit: int = 300) -> str:
            """List tracked source paths in one neutral revision."""
            return call("list_files", revision=revision, prefix=prefix, limit=limit)

        @server.tool()
        def read_code(revision: Revision, path: str, start_line: int = 1,
                      end_line: int | None = None) -> str:
            """Read at most 200 numbered source lines from one neutral revision."""
            return call("read_code", revision=revision, path=path,
                        start_line=start_line, end_line=end_line)

        @server.tool()
        def search_code(revision: Revision, pattern: str, path_glob: str | None = None,
                        ignore_case: bool = False) -> str:
            """Search tracked code with a git extended regular expression (at most 50 hits)."""
            return call("search_code", revision=revision, pattern=pattern,
                        path_glob=path_glob, ignore_case=ignore_case)

        @server.tool()
        def find_symbol(revision: Revision, name: str, path_glob: str | None = None) -> str:
            """Heuristically find a named function, method, class or type."""
            return call("find_symbol", revision=revision, name=name, path_glob=path_glob)

        @server.tool()
        def changed_files() -> str:
            """List tracked files changed between revision_A and revision_B."""
            return call("changed_files")

        @server.tool()
        def diff_file(path: str) -> str:
            """Show the neutral revision_A to revision_B diff for one file."""
            return call("diff_file", path=path)

        @server.tool()
        def map_location(from_revision: Revision, path: str, line: int) -> str:
            """Map an unchanged line to the other revision; changed hunks are reported, not guessed."""
            return call("map_location", from_revision=from_revision, path=path, line=line)

    if session.phase == "a":
        @server.tool()
        def submit_requirements(requirements: dict[str, Any]) -> str:
            """Validate and permanently lock entry, behavior and optional qualifier requirements."""
            return call("submit_requirements", requirements=requirements)
    elif session.phase == "b":
        @server.tool()
        def check_hop(hop: Hop) -> str:
            """Check one exact typed hop. Feedback is only confirmed/not confirmed/unable to confirm."""
            return call("check_hop", hop=_hop(hop))

        @server.tool()
        def submit_evidence(hops: list[Hop], requirement_doubt: str | None = None) -> str:
            """Permanently lock up to 12 distinct hops, all checked byte-identically in this turn."""
            return call("submit_evidence", hops=[_hop(h) for h in hops],
                        requirement_doubt=requirement_doubt)
    else:
        @server.tool()
        def submit_conclusion(conclusion: dict[str, Any]) -> str:
            """Permanently lock SUPPORTED, NOT_SUPPORTED or INDETERMINATE for both revisions."""
            return call("submit_conclusion", conclusion=conclusion)
    return server


def main() -> None:
    config = RDConfig.model_validate_json(Path(os.environ["SECREVIEW_SESSION"]).read_text())
    build_server(RDSession(config)).run("stdio")


if __name__ == "__main__":
    main()
