"""Build the synthetic-notes fixture repository deterministically.

    python fixtures/synthetic-notes/build.py [dest]   # default: .cache/fixtures/synthetic-notes

Two commits, tagged `base` and `head`. The head commit is a refactor that
moves note access into a service: GET keeps its ownership check (moved),
DELETE loses it (regression). users.py is renamed to accounts.py unchanged
in behavior, so its pre-existing email exposure survives.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = ROOT / ".cache" / "fixtures" / "synthetic-notes"

WEB = '''\
ROUTES = []


class Unauthorized(Exception):
    pass


class Forbidden(Exception):
    pass


def route(method, path):
    def register(fn):
        ROUTES.append((method, path, fn))
        return fn

    return register


def require_login(fn):
    def wrapper(request, *args, **kwargs):
        if request.user is None:
            raise Unauthorized()
        return fn(request, *args, **kwargs)

    wrapper.__name__ = fn.__name__
    return wrapper
'''

STORE = '''\
class NoteStore:
    def __init__(self):
        self._notes = {}

    def get(self, note_id):
        return self._notes[note_id]

    def delete(self, note_id):
        del self._notes[note_id]


class UserStore:
    def __init__(self):
        self._users = {}

    def all(self):
        return list(self._users.values())


notes = NoteStore()
users = UserStore()
'''

NOTES_BASE = '''\
from .store import notes
from .web import Forbidden, require_login, route


@route("GET", "/notes/<note_id>")
@require_login
def get_note(request, note_id):
    note = notes.get(note_id)
    if note.owner_id != request.user.id:
        raise Forbidden()
    return note


@route("DELETE", "/notes/<note_id>")
@require_login
def delete_note(request, note_id):
    note = notes.get(note_id)
    if note.owner_id != request.user.id:
        raise Forbidden()
    notes.delete(note_id)
    return {"deleted": note_id}
'''

NOTES_HEAD = '''\
from .services.notes_service import NotesService
from .store import notes
from .web import require_login, route

service = NotesService(notes)


@route("GET", "/notes/<note_id>")
@require_login
def get_note(request, note_id):
    return service.get_for(request.user, note_id)


@route("DELETE", "/notes/<note_id>")
@require_login
def delete_note(request, note_id):
    service.delete(note_id)
    return {"deleted": note_id}
'''

SERVICE = '''\
from ..web import Forbidden


class NotesService:
    def __init__(self, store):
        self.store = store

    def get_for(self, user, note_id):
        note = self.store.get(note_id)
        if note.owner_id != user.id:
            raise Forbidden()
        return note

    def delete(self, note_id):
        self.store.delete(note_id)
'''

USERS = '''\
from .store import users
from .web import require_login, route


@route("GET", "/users")
@require_login
def list_users(request):
    return [{"id": u.id, "email": u.email} for u in users.all()]
'''

APP_INIT_BASE = "from . import notes, users  # noqa: F401  (registers routes)\n"
APP_INIT_HEAD = "from . import accounts, notes  # noqa: F401  (registers routes)\n"

BASE_TREE = {
    "README.md": "# notes\n\nA tiny notes service.\n",
    "app/__init__.py": APP_INIT_BASE,
    "app/web.py": WEB,
    "app/store.py": STORE,
    "app/notes.py": NOTES_BASE,
    "app/users.py": USERS,
}

HEAD_TREE = {
    "README.md": "# notes\n\nA tiny notes service.\n\nNote access lives in `app/services`.\n",
    "app/__init__.py": APP_INIT_HEAD,
    "app/web.py": WEB,
    "app/store.py": STORE,
    "app/notes.py": NOTES_HEAD,
    "app/accounts.py": USERS,
    "app/services/__init__.py": "",
    "app/services/notes_service.py": SERVICE,
}


def _git(dest: Path, *args: str, date: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
    }
    out = subprocess.run(
        ["git", "-C", str(dest), *args], env=env, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _write_tree(dest: Path, tree: dict[str, str]) -> None:
    for child in dest.iterdir():
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    for rel, text in tree.items():
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)


def build(dest: Path = DEFAULT_DEST) -> dict[str, str]:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _git(dest, "init", "-q", "-b", "main", date="2026-01-01T00:00:00Z")
    commits = {}
    for tag, tree, date, msg in (
        ("base", BASE_TREE, "2026-01-01T00:00:00Z", "initial"),
        ("head", HEAD_TREE, "2026-01-02T00:00:00Z", "update"),
    ):
        _write_tree(dest, tree)
        _git(dest, "add", "-A", date=date)
        _git(dest, "commit", "-q", "--no-gpg-sign", "-m", msg, date=date)
        _git(dest, "tag", tag, date=date)
        commits[tag] = _git(dest, "rev-parse", "HEAD", date=date)
    return commits


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DEST
    for tag, sha in build(target).items():
        print(f"{tag} {sha}")
