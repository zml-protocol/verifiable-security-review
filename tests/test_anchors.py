import pytest

from spike.anchors import AnchorRegistry, CitationError, locate, verify

LINES = [
    "def delete_note(request, note_id):",
    "    note = notes.get(note_id)",
    "    if note.owner_id != request.user.id:",
    "        raise Forbidden()",
    "    notes.delete(note_id)",
]


def test_locate_fragment_and_multiline():
    assert locate(LINES, "notes.delete") == (4, 1)
    assert locate(LINES, "if note.owner_id != request.user.id:\n  raise Forbidden()") == (2, 2)
    # whitespace differences and the read_code gutter are tolerated
    assert locate(LINES, "   18 |     if note.owner_id  !=  request.user.id:") == (2, 1)
    assert locate(LINES, "-   18       |     if note.owner_id != request.user.id:") == (2, 1)


def test_locate_errors():
    with pytest.raises(CitationError) as e:
        locate(LINES, "note")
    assert e.value.code == "quote_ambiguous"
    with pytest.raises(CitationError) as e:
        locate(LINES, "is_admin(user)")
    assert e.value.code == "quote_not_found"
    with pytest.raises(CitationError) as e:
        locate(LINES, "  \n ")
    assert e.value.code == "quote_empty"


def test_registry_cite_narrows_and_verifies():
    reg = AnchorRegistry()
    a = reg.mint("base", "c0ffee", "app/notes.py", 16, LINES)
    narrowed = reg.cite(a.id, "if note.owner_id != request.user.id:\nraise Forbidden()")
    assert (narrowed.revision, narrowed.start_line, narrowed.end_line) == ("base", 18, 19)
    assert reg.get(narrowed.id) == narrowed
    file_lines = ["x"] * 15 + LINES
    assert verify(narrowed, file_lines)
    assert not verify(narrowed, ["x"] * 16 + LINES)
    with pytest.raises(CitationError) as e:
        reg.cite("Adeadbeef00")
    assert e.value.code == "unknown_anchor"


def test_same_code_on_both_sides_gets_distinct_anchors():
    reg = AnchorRegistry()
    a = reg.mint("base", "c0ffee", "f.py", 1, LINES)
    b = reg.mint("head", "c0ffee", "f.py", 1, LINES)
    assert a.id != b.id
    assert reg.get(a.id).revision == "base"
