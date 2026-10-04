"""Append-only phase-B checkpoint events and terminal checkpoint materialization for RD v3."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import rdv3_contract as contract


class CheckpointError(RuntimeError):
    pass


def _atomic_new(path: Path, data: bytes) -> None:
    """Publish a new immutable file atomically; an existing target is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise CheckpointError(f"refusing to overwrite checkpoint file {path.name}")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError as exc:
            raise CheckpointError(f"checkpoint target appeared concurrently: {path.name}") from exc
    finally:
        tmp.unlink(missing_ok=True)


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


class CheckpointLog:
    """One immutable event file per check_hop, chained by event digest."""

    def __init__(self, root: Path, *, task_id: str, session_id: str, a_seal: str,
                 provider_sha256: str, relation_table_sha256: str):
        self.root = root
        self.events_dir = root / "events"
        self.task_id = task_id
        self.session_id = session_id
        self.a_seal = a_seal
        self.provider_sha256 = provider_sha256
        self.relation_table_sha256 = relation_table_sha256
        self._events: list[dict] = []
        self._checked: dict[str, dict] = {}
        if root.exists() and any(root.rglob("*")):
            raise CheckpointError("a phase-B checkpoint directory must start empty")
        self.events_dir.mkdir(parents=True, exist_ok=True)
        meta = contract.sealed({
            "schema": "rd-v3-b-checkpoint-meta/v1", "task_id": task_id,
            "session_id": session_id, "a_seal": a_seal,
            "provider_sha256": provider_sha256,
            "relation_table_sha256": relation_table_sha256,
        })
        _atomic_new(root / "meta.json", _json_bytes(meta))

    def _verified_graph(self) -> list[dict]:
        return [copy.deepcopy(row) for row in self._checked.values()
                if row.get("state") == "VERIFIED"]

    def graph_sha256(self) -> str:
        return contract.seal({"verified_hops": self._verified_graph()})

    def append(self, *, proposed_hop: Any, state: str, elapsed_ms: int,
               tool_sequence: int, hop_check: int, checked: dict | None = None,
               error: dict | None = None) -> dict:
        if checked is not None:
            self._checked[checked["hop_sha256"]] = copy.deepcopy(checked)
        number = len(self._events) + 1
        body = {
            "schema": "rd-v3-b-checkpoint-event/v1",
            "event": number,
            "prior_event_sha256": self._events[-1]["event_sha256"] if self._events else None,
            "task_id": self.task_id,
            "revision": proposed_hop.get("revision") if isinstance(proposed_hop, dict) else None,
            "a_seal": self.a_seal,
            "provider_sha256": self.provider_sha256,
            "relation_table_sha256": self.relation_table_sha256,
            "proposed_hop": copy.deepcopy(proposed_hop),
            "checked": copy.deepcopy(checked),
            "resolution": {"state": state, **({"error": copy.deepcopy(error)} if error else {})},
            "graph_state_sha256": self.graph_sha256(),
            "phase_elapsed_ms": elapsed_ms,
            "tool_call": {"session_id": self.session_id, "phase": "b",
                          "sequence": tool_sequence, "hop_check": hop_check},
        }
        event = contract.sealed(body, field="event_sha256")
        _atomic_new(self.events_dir / f"{number:06d}.json", _json_bytes(event))
        self._events.append(event)
        return copy.deepcopy(event)

    def finalize(self, path: Path) -> dict:
        verified = self._verified_graph()
        body = {
            "schema": "rd-v3-b-partial-checkpoint/v1",
            "task_id": self.task_id,
            "a_seal": self.a_seal,
            "provider_sha256": self.provider_sha256,
            "relation_table_sha256": self.relation_table_sha256,
            "event_count": len(self._events),
            "last_event_sha256": self._events[-1]["event_sha256"] if self._events else None,
            "last_successful_event": max(
                (event["event"] for event in self._events
                 if event["resolution"]["state"] == "VERIFIED"), default=None),
            "graph_state_sha256": self.graph_sha256(),
            "checked_hops": [copy.deepcopy(row) for row in self._checked.values()],
            "verified_graph": verified,
        }
        artifact = contract.sealed(body)
        _atomic_new(path, _json_bytes(artifact))
        return artifact


def load_and_verify_events(root: Path) -> list[dict]:
    """Audit an event directory independently of a live session."""
    events, prior = [], None
    for expected, path in enumerate(sorted((root / "events").glob("*.json")), 1):
        if path.name != f"{expected:06d}.json":
            raise CheckpointError(f"non-canonical checkpoint event filename: {path.name}")
        event = json.loads(path.read_text())
        contract.verify_seal(event, field="event_sha256")
        if event.get("event") != expected or event.get("prior_event_sha256") != prior:
            raise CheckpointError(f"checkpoint event chain breaks at {path.name}")
        prior = event["event_sha256"]
        events.append(event)
    return events


def materialize(root: Path, path: Path) -> dict:
    """Reconstruct and seal the terminal partial graph after the phase-B process exits."""
    meta_path = root / "meta.json"
    if not meta_path.exists():
        raise CheckpointError("phase-B checkpoint metadata is missing")
    meta = json.loads(meta_path.read_text())
    contract.verify_seal(meta)
    events = load_and_verify_events(root)
    checked: dict[str, dict] = {}
    for event in events:
        for key in ("task_id", "a_seal", "provider_sha256", "relation_table_sha256"):
            if event.get(key) != meta.get(key):
                raise CheckpointError(f"checkpoint metadata drift in event {event['event']}: {key}")
        row = event.get("checked")
        if row is not None:
            if row.get("hop_sha256") != contract.seal(row.get("hop")):
                raise CheckpointError(f"bad checked-hop seal in event {event['event']}")
            checked[row["hop_sha256"]] = copy.deepcopy(row)
        verified_now = [copy.deepcopy(item) for item in checked.values()
                        if item.get("state") == "VERIFIED"]
        if event.get("graph_state_sha256") != contract.seal({"verified_hops": verified_now}):
            raise CheckpointError(f"graph-state drift in event {event['event']}")
    verified = [copy.deepcopy(item) for item in checked.values()
                if item.get("state") == "VERIFIED"]
    body = {
        "schema": "rd-v3-b-partial-checkpoint/v1",
        "task_id": meta["task_id"], "a_seal": meta["a_seal"],
        "provider_sha256": meta["provider_sha256"],
        "relation_table_sha256": meta["relation_table_sha256"],
        "event_count": len(events),
        "last_event_sha256": events[-1]["event_sha256"] if events else None,
        "last_successful_event": max(
            (event["event"] for event in events
             if event["resolution"]["state"] == "VERIFIED"), default=None),
        "graph_state_sha256": contract.seal({"verified_hops": verified}),
        "checked_hops": [copy.deepcopy(item) for item in checked.values()],
        "verified_graph": verified,
    }
    artifact = contract.sealed(body)
    _atomic_new(path, _json_bytes(artifact))
    return artifact


def materialize_terminal_b(artifact_dir: Path) -> dict:
    """Create the explicit C input for a valid B phase that ended without final submission."""
    final_path = artifact_dir / "b.json"
    if final_path.exists():
        final = json.loads(final_path.read_text())
        contract.verify_seal(final)
        return final
    checkpoint_path = artifact_dir / "partial-checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint_seal = contract.verify_seal(checkpoint)
    body = {
        "schema": "rd-v3-b-terminal/v1", "task_id": checkpoint["task_id"],
        "a_seal": checkpoint["a_seal"], "status": "B_TERMINAL_NO_SUBMIT",
        "partial_checkpoint_seal": checkpoint_seal,
        "partial_checkpoint": {key: copy.deepcopy(value) for key, value in checkpoint.items()
                               if key != "seal"},
    }
    terminal = contract.sealed(body)
    _atomic_new(artifact_dir / "b-terminal.json", _json_bytes(terminal))
    return terminal
