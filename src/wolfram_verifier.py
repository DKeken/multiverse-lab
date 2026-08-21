from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from hypothesis_compiler import CandidateError, verify_compiled_integrity
from local_verifier import to_wolfram


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def apply_wolfram_result(
    compiled: Mapping[str, Any],
    request_expression: str,
    response_text: str,
    expected_text: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach official Wolfram result without promoting empirical status."""
    verify_compiled_integrity(compiled)
    rendered_expression = to_wolfram(compiled)
    if request_expression != rendered_expression:
        raise CandidateError("WOLFRAM_REQUEST_MISMATCH")
    if compiled.get("status") != "locally_screened":
        raise CandidateError("WOLFRAM_REQUIRES_LOCAL_SCREEN")
    if type(request_expression) is not str or not request_expression.strip():
        raise CandidateError("WOLFRAM_REQUEST_INVALID")
    if type(response_text) is not str or type(expected_text) is not str:
        raise CandidateError("WOLFRAM_RESPONSE_INVALID")
    if type(provenance) is not dict or not all(
        type(provenance.get(key)) is str and provenance[key].strip()
        for key in ("tool", "endpoint", "observed_at_utc")
    ):
        raise CandidateError("WOLFRAM_PROVENANCE_REQUIRED")
    if "wolfram" not in provenance["tool"].lower():
        raise CandidateError("WOLFRAM_PROVENANCE_REQUIRED")

    result = copy.deepcopy(dict(compiled))
    normalized_response = response_text.strip()
    normalized_expected = expected_text.strip()
    result["wolfram_report"] = {
        "tool": provenance["tool"],
        "endpoint": provenance["endpoint"],
        "observed_at_utc": provenance["observed_at_utc"],
        "request_sha256": _hash_text(request_expression),
        "response_sha256": _hash_text(response_text),
        "expected_sha256": _hash_text(expected_text),
        "request_expression": request_expression,
        "response_text": response_text,
        "expected_text": expected_text,
        "scope": "independent mathematical check only; not empirical evidence",
    }
    if normalized_response == normalized_expected:
        result["status"] = "wolfram_verified"
        result["status_history"] = ["generated", "schema_valid", "locally_screened", "wolfram_verified"]
        result["rejection_codes"] = []
    elif normalized_response in {"True", "False"} and normalized_expected in {"True", "False"}:
        result["status"] = "cas_disagreement"
        result["status_history"] = ["generated", "schema_valid", "locally_screened", "cas_disagreement"]
        result["rejection_codes"] = ["CAS_DISAGREEMENT"]
    else:
        result["status"] = "locally_screened"
        result["status_history"] = ["generated", "schema_valid", "locally_screened"]
        result["rejection_codes"] = ["WOLFRAM_UNRESOLVED"]
    result.pop("observational_evidence", None)
    return result
