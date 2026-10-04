import asyncio
import re

from mcp import Client

from spike.mcp_server import build_server


def test_tools_round_trip_over_mcp(make_session):
    session = make_session("H1")

    async def run():
        async with Client(build_server(session)) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert {"get_task", "read_code", "submit_observation", "finish"} <= names
            read = await client.call_tool(
                "read_code", {"revision": "base", "path": "app/notes.py", "start_line": 14}
            )
            text = read.content[0].text
            assert "    18 |     if note.owner_id != request.user.id:" in text
            anchor = re.match(r"anchor (A[0-9a-f]{10})  revision=base", text)[1]
            ok = await client.call_tool(
                "submit_observation",
                {
                    "revision": "base",
                    "component": "control",
                    "stance": "contradicts",
                    "statement": "owner check",
                    "citations": [{"anchor_id": anchor, "quote": "raise Forbidden()"}],
                },
            )
            assert not ok.is_error
            bad = await client.call_tool(
                "submit_observation",
                {
                    "revision": "head",
                    "component": "control",
                    "stance": "supports",
                    "statement": "x",
                    "citations": [{"anchor_id": anchor}],
                },
            )
            assert bad.is_error
            assert "[revision_mismatch]" in bad.content[0].text

    asyncio.run(run())
    assert len(session.observations) == 1
