from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from hypothesis_compiler import compile_candidate

STATUSES = (
    "generated", "schema_valid", "locally_screened", "wolfram_verified",
    "cas_disagreement", "simulation_eligible", "rejected", "empirically_supported",
)
TRANSITIONS = {
    "generated": {"schema_valid", "rejected"},
    "schema_valid": {"locally_screened", "rejected"},
    "locally_screened": {"wolfram_verified", "cas_disagreement", "rejected"},
    "wolfram_verified": {"simulation_eligible", "cas_disagreement", "rejected"},
    "simulation_eligible": {"simulation_eligible", "empirically_supported", "rejected"},
    "cas_disagreement": set(), "rejected": set(), "empirically_supported": set(),
}
REQUIRED_EVENT_FIELDS = {
    "event_id", "candidate_id", "occurred_at", "gate_id", "status", "epistemic_class",
    "input_hash", "output_hash", "artifact_refs",
}


class ArchiveError(ValueError):
    pass


class StatusTransitionError(ArchiveError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArchiveError(f"not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class HypothesisArchive:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.schema_path = Path(__file__).resolve().parents[1] / "research" / "hypothesis.schema.json"

    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        event = self._validate_input(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                events = self._read_unlocked()
                stored = self._prepare(event, events)
                if stored.get("_existing"):
                    stored.pop("_existing")
                    return stored
                line = canonical_bytes(stored) + b"\n"
                descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    os.write(descriptor, line)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                return copy.deepcopy(stored)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def elites(self) -> list[dict[str, Any]]:
        current = self._current(self._read_locked())
        selected: dict[tuple[str, ...], tuple[float, str, dict[str, Any]]] = {}
        for event in current.values():
            if event["status"] in {"generated", "rejected", "cas_disagreement"}:
                continue
            hypothesis = event.get("hypothesis", {})
            niche_data = event.get("niche") if isinstance(event.get("niche"), dict) else {}
            niche = (
                str(hypothesis.get("domain", "unknown")),
                str(niche_data.get("cost_band", "unknown")),
                str(niche_data.get("mechanism", "unknown")),
                str(niche_data.get("scale", "unknown")),
                str(niche_data.get("falsifier", hypothesis.get("falsifier", "unknown"))),
            )
            score = event.get("quality_score", 0.0)
            score = float(score) if type(score) in (int, float) and math.isfinite(score) else 0.0
            contender = (score, event["archive"]["event_sha256"], event)
            incumbent = selected.get(niche)
            if incumbent is None or contender[0] > incumbent[0] or (contender[0] == incumbent[0] and contender[1] < incumbent[1]):
                selected[niche] = contender
        return [copy.deepcopy(selected[key][2]) for key in sorted(selected)]

    def failure_seen(self, signature: Any) -> bool:
        signature_hash = digest(signature)
        return any(event.get("rejection", {}).get("signature_sha256") == signature_hash for event in self._read_locked())

    def _validate_input(self, record: Mapping[str, Any]) -> dict[str, Any]:
        if type(record) is not dict:
            raise ArchiveError("event must be a plain object")
        event = copy.deepcopy(record)
        missing = REQUIRED_EVENT_FIELDS - event.keys()
        if missing:
            raise ArchiveError(f"missing event fields: {sorted(missing)}")
        if event.keys() - (REQUIRED_EVENT_FIELDS | {"parent_event_id", "hypothesis", "rejection", "tool_provenance", "observational_evidence", "niche", "quality_score"}):
            raise ArchiveError("unexpected event fields")
        if event["status"] not in STATUSES:
            raise ArchiveError("invalid status")
        if event["epistemic_class"] not in {"ESTABLISHED", "ADAPTED", "NOVEL PROPOSAL", "UNVERIFIED"}:
            raise ArchiveError("invalid epistemic_class")
        for field in ("event_id", "candidate_id", "occurred_at", "gate_id", "input_hash", "output_hash"):
            if type(event[field]) is not str or not event[field].strip():
                raise ArchiveError(f"invalid {field}")
        if type(event["artifact_refs"]) is not list or not all(type(item) is str for item in event["artifact_refs"]):
            raise ArchiveError("artifact_refs must be string array")
        if event["status"] in {"generated", "schema_valid"} and type(event.get("hypothesis")) is not dict:
            raise ArchiveError("generated/schema_valid event requires hypothesis")
        if event["status"] in {"rejected", "cas_disagreement"} and type(event.get("rejection")) is not dict:
            raise ArchiveError("terminal failure requires rejection metadata")
        if event["status"] == "wolfram_verified" and not event.get("tool_provenance", {}).get("wolfram"):
            raise ArchiveError("wolfram_verified requires Wolfram provenance")
        if event["status"] == "empirically_supported":
            evidence = event.get("observational_evidence")
            if type(evidence) is not dict or not all(evidence.get(key) for key in ("dataset_sha256", "freeze_hash", "result_hash")):
                raise ArchiveError("empirically_supported requires observation provenance")
        if event["status"] not in {"generated", "rejected"}:
            compiled = compile_candidate(event.get("hypothesis"), self.schema_path)
            if compiled["status"] != "schema_valid":
                raise ArchiveError(f"hypothesis schema invalid: {compiled['rejection_codes']}")
        if "rejection" in event:
            rejection = event["rejection"]
            if type(rejection) is not dict or not all(rejection.get(key) for key in ("reason_code", "falsified_assumption", "evidence_ref")):
                raise ArchiveError("rejection metadata incomplete")
            rejection["signature_sha256"] = digest({key: rejection[key] for key in ("reason_code", "falsified_assumption")})
        return event

    def _prepare(self, event: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        if any(item["event_id"] == event["event_id"] for item in events):
            existing = next(item for item in events if item["event_id"] == event["event_id"])
            if digest({k: v for k, v in existing.items() if k != "archive"}) != digest(event):
                raise ArchiveError("event_id collision")
            copy_event = copy.deepcopy(existing)
            copy_event["_existing"] = True
            return copy_event
        current = self._current(events).get(event["candidate_id"])
        if current is None:
            if event["status"] != "generated" or "parent_event_id" in event:
                raise StatusTransitionError("candidate must begin at generated without parent")
        else:
            if event.get("parent_event_id") != current["event_id"]:
                raise StatusTransitionError("parent_event_id must name current event")
            if event["status"] not in TRANSITIONS[current["status"]]:
                raise StatusTransitionError(f"invalid transition {current['status']} -> {event['status']}")
            if event.get("hypothesis", current.get("hypothesis")) != current.get("hypothesis"):
                raise ArchiveError("hypothesis content is immutable")
            event.setdefault("hypothesis", copy.deepcopy(current.get("hypothesis")))
        previous_hash = events[-1]["archive"]["event_sha256"] if events else None
        event["archive"] = {"sequence": len(events) + 1, "previous_event_sha256": previous_hash}
        event["archive"]["event_sha256"] = digest(event)
        return event

    def _read_locked(self) -> list[dict[str, Any]]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
            try:
                return self._read_unlocked()
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        previous = None
        with self.path.open("rb") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ArchiveError(f"invalid JSONL line {number}") from exc
                archive = event.get("archive", {})
                supplied = archive.get("event_sha256")
                unhashed = copy.deepcopy(event)
                unhashed.get("archive", {}).pop("event_sha256", None)
                if archive.get("sequence") != number or archive.get("previous_event_sha256") != previous or supplied != digest(unhashed):
                    raise ArchiveError(f"broken archive chain at line {number}")
                previous = supplied
                events.append(event)
        return events

    @staticmethod
    def _current(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        current = {}
        for event in events:
            current[event["candidate_id"]] = event
        return current
