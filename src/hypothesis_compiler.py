from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_AST_DEPTH = 12
MAX_AST_NODES = 256
MAX_COST = {"data_gb": 10.0, "cpu_hours": 24.0, "gpu_hours": 0.0}
ALLOWED_DOMAINS = {
    "cmb",
    "quantum-foundations",
    "gravitational-waves",
    "cosmic-topology",
    "analogue-gravity",
    "general-relativity",
}
ALLOWED_CLASSIFICATIONS = {"NOVEL PROPOSAL", "UNVERIFIED"}
ALLOWED_ROLES = {"definition", "constraint", "prediction", "conservation"}
ALLOWED_SYMBOL_DOMAINS = {"real", "positive", "nonnegative", "angle"}
SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")


class CandidateError(ValueError):
    def __init__(self, *codes: str) -> None:
        self.codes = tuple(sorted(set(codes)))
        super().__init__(", ".join(self.codes))


def _duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateError("DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise CandidateError("NONFINITE_NUMBER")


def _strict_load(raw: str | bytes | bytearray) -> Any:
    payload = bytes(raw) if not isinstance(raw, str) else raw.encode("utf-8")
    if len(payload) > MAX_INPUT_BYTES:
        raise CandidateError("INPUT_TOO_LARGE")
    try:
        text = payload.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except CandidateError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateError("JSON_INVALID") from exc


def _plain_json(value: Any, depth: int = 0) -> Any:
    if depth > MAX_AST_DEPTH + 8:
        raise CandidateError("INPUT_TOO_DEEP")
    if value is None or type(value) is bool or type(value) is str:
        return value
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise CandidateError("NONFINITE_NUMBER")
        if abs(value) > 1e300:
            raise CandidateError("NUMBER_MAGNITUDE")
        return value
    if type(value) is list:
        return [_plain_json(item, depth + 1) for item in value]
    if type(value) is dict:
        if not all(type(key) is str for key in value):
            raise CandidateError("JSON_KEY_TYPE")
        return {key: _plain_json(item, depth + 1) for key, item in value.items()}
    raise CandidateError("JSON_TYPE")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_schema(path: str | Path) -> dict[str, Any]:
    schema_path = Path(path)
    schema = _strict_load(schema_path.read_bytes())
    schema = _plain_json(schema)
    if type(schema) is not dict:
        raise CandidateError("SCHEMA_INVALID")
    return schema


def _text(value: Any, minimum: int, maximum: int, code: str) -> str:
    if type(value) is not str or value != value.strip() or not minimum <= len(value) <= maximum:
        raise CandidateError(code)
    return value


def _number(value: Any, code: str) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise CandidateError(code)
    return value


def _keys(value: Any, required: set[str], allowed: set[str], prefix: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CandidateError(f"{prefix}_TYPE")
    missing = required - value.keys()
    extra = value.keys() - allowed
    codes = []
    if missing:
        codes.append(f"{prefix}_REQUIRED")
    if extra:
        codes.append("SCHEMA_EXTRA_PROPERTY")
    if codes:
        raise CandidateError(*codes)
    return value


def _validate_expression(node: Any, symbols: set[str], depth: int, counter: list[int]) -> dict[str, Any]:
    if depth > MAX_AST_DEPTH:
        raise CandidateError("AST_TOO_DEEP")
    counter[0] += 1
    if counter[0] > MAX_AST_NODES:
        raise CandidateError("AST_TOO_LARGE")
    value = _keys(node, set(), {"number", "symbol", "op", "args", "base", "exponent", "arg"}, "AST")
    if set(value) == {"number"}:
        _number(value["number"], "NONFINITE_NUMBER")
        return value
    if set(value) == {"symbol"}:
        symbol = value["symbol"]
        if type(symbol) is not str or not SYMBOL_RE.fullmatch(symbol):
            raise CandidateError("SYMBOL_INVALID")
        if symbol not in symbols:
            raise CandidateError("SYMBOL_UNDECLARED")
        return value
    op = value.get("op")
    if op in {"add", "mul"} and set(value) == {"op", "args"}:
        args = value["args"]
        if type(args) is not list or not 2 <= len(args) <= 12:
            raise CandidateError("AST_ARITY")
        for argument in args:
            _validate_expression(argument, symbols, depth + 1, counter)
        return value
    if op == "pow" and set(value) == {"op", "base", "exponent"}:
        _number(value["exponent"], "POWER_EXPONENT")
        _validate_expression(value["base"], symbols, depth + 1, counter)
        return value
    if op in {"sin", "cos", "exp", "log", "neg"} and set(value) == {"op", "arg"}:
        _validate_expression(value["arg"], symbols, depth + 1, counter)
        return value
    raise CandidateError("OP_NOT_ALLOWED")


def _validate_candidate(candidate: Any) -> dict[str, Any]:
    required = {
        "id", "title", "classification", "domain", "claim", "assumptions",
        "symbols", "equations", "observable", "falsifier", "rivals", "cost",
    }
    value = _keys(candidate, required, required, "SCHEMA")
    if type(value["id"]) is not str or not ID_RE.fullmatch(value["id"]):
        raise CandidateError("ID_INVALID")
    _text(value["title"], 8, 160, "TITLE_INVALID")
    if value["classification"] not in ALLOWED_CLASSIFICATIONS:
        raise CandidateError("CLASSIFICATION_INVALID")
    if value["domain"] not in ALLOWED_DOMAINS:
        raise CandidateError("DOMAIN_INVALID")
    _text(value["claim"], 20, 800, "CLAIM_INVALID")
    assumptions = value["assumptions"]
    if type(assumptions) is not list or not 1 <= len(assumptions) <= 12:
        raise CandidateError("ASSUMPTIONS_INVALID")
    for assumption in assumptions:
        _text(assumption, 3, 240, "ASSUMPTIONS_INVALID")

    symbols = value["symbols"]
    if type(symbols) is not dict or not 1 <= len(symbols) <= 40:
        raise CandidateError("SYMBOLS_INVALID")
    for name, declaration in symbols.items():
        if type(name) is not str or not SYMBOL_RE.fullmatch(name):
            raise CandidateError("SYMBOL_INVALID")
        declaration = _keys(declaration, {"dimension", "domain"}, {"dimension", "domain", "min", "max"}, "SYMBOL")
        dimension = declaration["dimension"]
        if type(dimension) is not list or len(dimension) != 4:
            raise CandidateError("DIMENSION_INVALID")
        for exponent in dimension:
            _number(exponent, "DIMENSION_INVALID")
        if declaration["domain"] not in ALLOWED_SYMBOL_DOMAINS:
            raise CandidateError("SYMBOL_DOMAIN_INVALID")
        minimum = declaration.get("min")
        maximum = declaration.get("max")
        if minimum is not None:
            _number(minimum, "INVALID_SYMBOL_BOUNDS")
        if maximum is not None:
            _number(maximum, "INVALID_SYMBOL_BOUNDS")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise CandidateError("INVALID_SYMBOL_BOUNDS")
        if declaration["domain"] == "positive" and (minimum is None or minimum <= 0):
            raise CandidateError("INVALID_SYMBOL_BOUNDS")
        if declaration["domain"] == "nonnegative" and minimum is not None and minimum < 0:
            raise CandidateError("INVALID_SYMBOL_BOUNDS")
        if declaration["domain"] == "angle" and any(exponent != 0 for exponent in dimension):
            raise CandidateError("ANGLE_DIMENSIONFUL")

    equations = value["equations"]
    if type(equations) is not list or not 1 <= len(equations) <= 16:
        raise CandidateError("EQUATIONS_INVALID")
    counter = [0]
    for equation in equations:
        equation = _keys(equation, {"lhs", "rhs", "role"}, {"lhs", "rhs", "role"}, "EQUATION")
        if equation["role"] not in ALLOWED_ROLES:
            raise CandidateError("EQUATION_ROLE")
        _validate_expression(equation["lhs"], set(symbols), 1, counter)
        _validate_expression(equation["rhs"], set(symbols), 1, counter)

    observable = _keys(value["observable"], {"quantity", "dataset", "signature", "decision_rule"}, {"quantity", "dataset", "signature", "decision_rule"}, "OBSERVABLE")
    _text(observable["quantity"], 2, 120, "OBSERVABLE_REQUIRED")
    _text(observable["dataset"], 2, 240, "OBSERVABLE_REQUIRED")
    _text(observable["signature"], 10, 500, "OBSERVABLE_REQUIRED")
    _text(observable["decision_rule"], 10, 500, "OBSERVABLE_REQUIRED")
    _text(value["falsifier"], 10, 500, "FALSIFIER_REQUIRED")
    rivals = value["rivals"]
    if type(rivals) is not list or not 1 <= len(rivals) <= 10:
        raise CandidateError("RIVAL_REQUIRED")
    for rival in rivals:
        _text(rival, 3, 200, "RIVAL_REQUIRED")
    cost = _keys(value["cost"], set(MAX_COST), set(MAX_COST), "COST")
    for key, maximum in MAX_COST.items():
        number = _number(cost[key], f"COST_{key.upper()}_INVALID")
        if number < 0 or number > maximum:
            raise CandidateError(f"COST_{key.upper()}_EXCEEDED")
    return value


def _rejected(codes: tuple[str, ...], schema_hash: str | None = None) -> dict[str, Any]:
    return {
        "status": "rejected",
        "status_history": ["generated", "rejected"],
        "rejection_codes": list(sorted(set(codes))),
        "schema_sha256": schema_hash,
    }


def compile_candidate(raw: Any, schema_path: str | Path) -> dict[str, Any]:
    try:
        schema_bytes = Path(schema_path).read_bytes()
        schema = load_schema(schema_path)
        schema_hash = _sha256_bytes(_canonical_bytes(schema))
        if isinstance(raw, (str, bytes, bytearray)):
            candidate = _strict_load(raw)
        else:
            candidate = _plain_json(copy.deepcopy(raw))
        candidate = _validate_candidate(candidate)
        canonical = _canonical_bytes(candidate)
        if len(canonical) > MAX_INPUT_BYTES:
            raise CandidateError("INPUT_TOO_LARGE")
        normalized_json = canonical.decode("utf-8")
        return {
            "status": "schema_valid",
            "status_history": ["generated", "schema_valid"],
            "candidate": candidate,
            "normalized_json": normalized_json,
            "content_sha256": _sha256_bytes(canonical),
            "schema_sha256": schema_hash,
            "rejection_codes": [],
        }
    except CandidateError as exc:
        return _rejected(exc.codes, locals().get("schema_hash"))
    except OSError:
        return _rejected(("SCHEMA_UNAVAILABLE",), None)


def verify_compiled_integrity(compiled: Mapping[str, Any]) -> dict[str, Any]:
    if type(compiled) is not dict or compiled.get("status") not in {"schema_valid", "locally_screened"}:
        raise CandidateError("COMPILED_STATUS_INVALID")
    normalized = compiled.get("normalized_json")
    if type(normalized) is not str:
        raise CandidateError("NORMALIZED_JSON_MISSING")
    candidate = _strict_load(normalized)
    candidate = _plain_json(candidate)
    if candidate != compiled.get("candidate"):
        raise CandidateError("CONTENT_HASH_MISMATCH")
    canonical = _canonical_bytes(candidate)
    if canonical.decode("utf-8") != normalized or _sha256_bytes(canonical) != compiled.get("content_sha256"):
        raise CandidateError("CONTENT_HASH_MISMATCH")
    return candidate
