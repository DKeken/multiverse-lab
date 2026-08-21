from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

STATUS_GATE = {
    "generated": "schema_validation",
    "schema_valid": "local_screen",
    "locally_screened": "wolfram_verification",
    "wolfram_verified": "low_fidelity_simulation",
    "simulation_eligible": "next_simulation_or_observation",
}
TERMINAL = {"rejected", "cas_disagreement", "empirically_supported"}


class SchedulerError(ValueError):
    pass


def _finite_number(value: Any, default: float = 0.0) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        return default
    return float(value)


def plan_evaluations(
    records: Iterable[Mapping[str, Any]],
    gate_specs: Iterable[Mapping[str, Any]],
    budget: Mapping[str, Any],
) -> list[dict[str, Any]]:
    specs = {str(item["id"]): dict(item) for item in gate_specs if type(item) is dict and "id" in item}
    remaining = {
        "wall_seconds": _finite_number(budget.get("wall_seconds")),
        "cpu_hours": _finite_number(budget.get("cpu_hours")),
        "data_gb": _finite_number(budget.get("data_gb")),
        "paid_usd": _finite_number(budget.get("paid_usd")),
    }
    remote_slots = int(_finite_number(budget.get("remote_llm_jobs", 1), 1))
    if remote_slots > 1:
        remote_slots = 1
    candidates = []
    for record in records:
        if type(record) is not dict:
            continue
        status = record.get("status")
        candidate_id = str(record.get("candidate_id", ""))
        if not candidate_id or status in TERMINAL:
            continue
        requested_gate = record.get("next_gate") or STATUS_GATE.get(str(status))
        if requested_gate not in specs:
            candidates.append({"candidate_id": candidate_id, "decision": "deferred", "reason": "NO_ELIGIBLE_GATE"})
            continue
        spec = specs[requested_gate]
        prerequisites = set(spec.get("requires_status", []))
        if prerequisites and status not in prerequisites:
            candidates.append({"candidate_id": candidate_id, "gate_id": requested_gate, "decision": "deferred", "reason": "PREREQUISITE_STATUS"})
            continue
        if spec.get("remote_llm") and remote_slots <= 0:
            candidates.append({"candidate_id": candidate_id, "gate_id": requested_gate, "decision": "deferred", "reason": "REMOTE_CONCURRENCY"})
            continue
        cost = {key: _finite_number(spec.get("cost", {}).get(key)) for key in remaining}
        if any(cost[key] < 0 for key in cost):
            raise SchedulerError("negative gate cost")
        p_pass = min(1.0, max(0.0, _finite_number(record.get("p_pass"), 0.5)))
        information = max(0.0, _finite_number(record.get("expected_information_bits"), 0.0))
        novelty = max(0.0, _finite_number(record.get("novelty_weight"), 1.0))
        reproducibility = max(0.0, _finite_number(record.get("reproducibility_weight"), 1.0))
        denominator = max(1.0, cost["wall_seconds"] + 3600 * cost["paid_usd"] + 60 * cost["data_gb"])
        priority = p_pass * information * novelty * reproducibility / denominator
        candidates.append({
            "candidate_id": candidate_id,
            "gate_id": requested_gate,
            "decision": "eligible",
            "priority": priority,
            "cost": cost,
            "remote_llm": bool(spec.get("remote_llm")),
            "reason": "CHEAPEST_ELIGIBLE_DECISIVE_GATE",
        })
    predeferred = [item for item in candidates if item["decision"] != "eligible"]
    eligible = sorted(
        (item for item in candidates if item["decision"] == "eligible"),
        key=lambda item: (-item["priority"], item["cost"]["wall_seconds"], item["candidate_id"], item["gate_id"]),
    )
    planned = []
    for item in eligible:
        if any(item["cost"][key] > remaining[key] for key in remaining):
            item["decision"] = "deferred"
            item["reason"] = "BUDGET_RESERVATION_FAILED"
        elif item["remote_llm"] and remote_slots <= 0:
            item["decision"] = "deferred"
            item["reason"] = "REMOTE_CONCURRENCY"
        else:
            item["decision"] = "scheduled"
            for key in remaining:
                remaining[key] -= item["cost"][key]
            if item["remote_llm"]:
                remote_slots -= 1
        planned.append(item)
    planned.extend(predeferred)
    return planned
