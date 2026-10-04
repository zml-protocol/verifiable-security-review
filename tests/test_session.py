import json

import pytest

from spike.session import ToolInputError


def _error(session, tool, **args):
    with pytest.raises(ToolInputError) as e:
        session.call(tool, **args)
    return e.value.code


def test_read_cite_and_submit(make_session):
    s = make_session("H1")
    task = s.call("get_task")
    assert [c["id"] for c in task["hypothesis"]["components"]] == ["entrypoint", "control", "effect"]

    base = s.call("read_code", revision="base", path="app/notes.py", start_line=14)
    assert base["anchor"]["lines"] == "14-21"
    assert "    18 |     if note.owner_id != request.user.id:" in base["code"]

    obs = s.call(
        "submit_observation",
        revision="base",
        component="control",
        stance="contradicts",
        statement="delete_note checks ownership before deleting",
        citations=[{"anchor_id": base["anchor"]["id"], "quote": "if note.owner_id != request.user.id:\nraise Forbidden()"}],
    )
    assert obs["citations"][0]["lines"] == "18-19"

    state = json.loads((s.out_dir / "state.json").read_text())
    assert state["observations"][0]["citations"][0]["start_line"] == 18
    assert all(a["commit"] == s.commits[a["revision"]] for a in state["anchors"])


def test_rejections_are_logged_with_codes(make_session):
    s = make_session("H1")
    head = s.call("read_code", revision="head", path="app/notes.py")
    # citing head code in a base observation is the base/head confusion we measure
    assert _error(
        s, "submit_observation", revision="base", component="control", stance="supports",
        statement="x", citations=[{"anchor_id": head["anchor"]["id"]}],
    ) == "revision_mismatch"
    assert _error(
        s, "submit_observation", revision="head", component="control", stance="supports",
        statement="x", citations=[{"anchor_id": "A0000000000"}],
    ) == "unknown_anchor"
    assert _error(
        s, "submit_observation", revision="head", component="control", stance="supports",
        statement="x", citations=[{"anchor_id": head["anchor"]["id"], "quote": "is_admin"}],
    ) == "quote_not_found"
    assert _error(
        s, "submit_observation", revision="head", component="nope", stance="unclear", statement="x"
    ) == "bad_component"
    assert _error(
        s, "submit_observation", revision="head", component="control", stance="supports", statement="x"
    ) == "missing_citation"
    codes = [
        json.loads(line).get("error", {}).get("code")
        for line in (s.out_dir / "transcript.jsonl").read_text().splitlines()
    ]
    assert codes == [None, "revision_mismatch", "unknown_anchor", "quote_not_found",
                     "bad_component", "missing_citation"]


def test_diff_hunks_carry_anchors_for_both_sides(make_session):
    s = make_session("H1")
    changed = {f["head_path"] or f["base_path"]: f for f in s.call("changed_files")["files"]}
    assert changed["app/accounts.py"]["status"] == "R"
    assert changed["app/accounts.py"]["base_path"] == "app/users.py"
    assert changed["app/services/notes_service.py"]["status"] == "A"

    diff = s.call("diff_file", path="app/notes.py")
    hunk = diff["hunks"][0]
    assert "-   18       |     if note.owner_id != request.user.id:" in hunk["diff"]
    base_anchor = hunk["base_anchor"]["id"]
    # the owner check appears twice in the base side of the hunk
    assert _error(
        s, "submit_observation", revision="base", component="control", stance="contradicts",
        statement="x", citations=[{"anchor_id": base_anchor, "quote": "if note.owner_id != request.user.id:"}],
    ) == "quote_ambiguous"
    obs = s.call(
        "submit_observation", revision="base", component="control", stance="contradicts",
        statement="owner check guards the delete",
        citations=[{"anchor_id": base_anchor, "quote": "raise Forbidden()\n    notes.delete(note_id)"}],
    )
    assert obs["citations"][0]["lines"] == "19-20"


def test_map_location_search_and_symbols(make_session):
    s = make_session("H1")
    assert s.call("map_location", from_revision="base", path="app/notes.py", line=7)["to_line"] == 10
    m = s.call("map_location", from_revision="base", path="app/notes.py", line=18)
    assert m["status"] == "in_hunk" and m["changed_lines"] == {"base": "17-20", "head": "17-17"}

    hits = s.call("find_symbol", revision="head", name="NotesService.delete")["hits"]
    assert {(h["path"], h["line"]) for h in hits} >= {("app/services/notes_service.py", 14)}
    hits = s.call("search_code", revision="head", pattern=r"owner_id\s*!=", path_glob="app/**")["hits"]
    assert [(h["path"], h["line"]) for h in hits] == [("app/services/notes_service.py", 10)]
    # a search hit is itself citable
    s.call(
        "submit_observation", revision="head", component="control", stance="unclear",
        statement="only one owner check remains", citations=[{"anchor_id": hits[0]["anchor"]}],
    )


def test_deny_policy_and_bad_paths(make_session):
    s = make_session("H1", deny=["README*"])
    assert "README.md" not in s.call("list_files", revision="head")["files"]
    assert _error(s, "read_code", revision="head", path="README.md") == "path_denied"
    assert _error(s, "read_code", revision="head", path="../etc/passwd") == "bad_path"
    assert _error(s, "read_code", revision="head", path="app/users.py") == "not_found"
    assert _error(s, "read_code", revision="side", path="app/web.py") == "bad_revision"


def test_identity_condition_has_no_changes(make_session):
    s = make_session("H1", base="head", head="head")
    assert s.call("changed_files") == {"files": []}
    a = s.call("read_code", revision="base", path="app/notes.py")
    b = s.call("read_code", revision="head", path="app/notes.py")
    assert a["anchor"]["id"] != b["anchor"]["id"]


def test_finish_closes_session(make_session):
    s = make_session("H2")
    s.call("finish", summary="done")
    assert _error(s, "read_code", revision="head", path="app/web.py") == "session_finished"
    assert s.call("get_task")["hypothesis"]["id"] == "H2"


def test_malformed_pattern_is_an_input_error(make_session):
    s = make_session("H1")
    assert _error(s, "search_code", revision="head", pattern="Contains(.*x") == "bad_pattern"
    assert _error(s, "search_code", revision="head", pattern="a[") == "bad_pattern"
    last = json.loads((s.out_dir / "transcript.jsonl").read_text().splitlines()[-1])
    assert last["error"]["code"] == "bad_pattern"
    assert "Invalid regular expression" in last["error"]["message"]
