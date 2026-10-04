from spike.gitrepo import GitRepo, Hunk
from spike.linemap import LineMap, MapStatus, translate


def test_translate_insertion_shifts_following_lines():
    hunks = [Hunk(4, 0, 5, 2)]  # two lines inserted after old line 4
    assert translate(hunks, 4, "base") == (4, None)
    assert translate(hunks, 5, "base") == (7, None)
    assert translate(hunks, 5, "head")[1] == hunks[0]
    assert translate(hunks, 7, "head") == (5, None)


def test_translate_deletion_and_modification():
    hunks = [Hunk(3, 2, 2, 0), Hunk(10, 1, 8, 3)]  # delete old 3-4; old 10 -> new 8-10
    assert translate(hunks, 2, "base") == (2, None)
    assert translate(hunks, 3, "base")[1] == hunks[0]
    assert translate(hunks, 5, "base") == (3, None)
    assert translate(hunks, 10, "base")[1] == hunks[1]
    assert translate(hunks, 11, "base") == (11, None)
    assert translate(hunks, 11, "head") == (11, None)
    assert translate(hunks, 9, "head")[1] == hunks[1]


def test_linemap_on_fixture(notes_repo):
    repo = GitRepo(notes_repo)
    lm = LineMap(repo, repo.resolve("base"), repo.resolve("head"))
    # def get_note: base line 7 sits at head line 10 after inserted imports
    m = lm.map("app/notes.py", 7, "base")
    assert (m.status, m.to_path, m.to_line) == (MapStatus.TRANSLATED, "app/notes.py", 10)
    assert lm.map("app/notes.py", 18, "base").status is MapStatus.IN_HUNK
    m = lm.map("app/accounts.py", 8, "head")
    assert (m.status, m.to_path, m.to_line) == (MapStatus.TRANSLATED, "app/users.py", 8)
    assert lm.map("app/services/notes_service.py", 3, "head").status is MapStatus.FILE_ABSENT
    assert lm.map("app/web.py", 20, "base").status is MapStatus.UNCHANGED_FILE
    assert lm.changed_span("app/notes.py", "base") == [(2, 2), (8, 11), (17, 20)]
