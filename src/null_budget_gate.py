from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


class NullBudgetError(ValueError):
    pass


def _plain_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise NullBudgetError(f"{name} must be a plain object")
    return value


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise NullBudgetError(f"{name} must be an integer >= {minimum}")
    return value


def _probability(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise NullBudgetError(f"invalid alpha {text!r}") from exc
    if not value.is_finite() or not Decimal(0) < value < Decimal(1):
        raise NullBudgetError("alpha must be finite and between zero and one")
    return value


def _minimum_budget(k: int, alpha: Decimal) -> int:
    required_denominator = (Decimal(k + 1) / alpha).to_integral_value(rounding="ROUND_CEILING")
    return int(required_denominator) - 1


def certify_null_budget(
    result: Mapping[str, Any],
    maximum_final_budget: int,
    alpha_texts: Sequence[str],
) -> dict[str, Any]:
    maximum_final_budget = _integer(maximum_final_budget, "maximum_final_budget", 1)
    pipeline = _plain_mapping(result.get("pipeline"), "pipeline")
    global_pilot = _plain_mapping(result.get("global_pilot"), "global_pilot")
    n = _integer(pipeline.get("null_simulations"), "null_simulations", 1)
    k = _integer(global_pilot.get("null_exceedances"), "null_exceedances")
    if k > n:
        raise NullBudgetError("null_exceedances cannot exceed null_simulations")
    if maximum_final_budget < n:
        raise NullBudgetError("maximum_final_budget cannot be below completed simulations")
    empirical_p = global_pilot.get("empirical_p")
    if type(empirical_p) not in (int, float) or not math.isfinite(empirical_p):
        raise NullBudgetError("empirical_p must be finite")
    exact_current_p = (k + 1) / (n + 1)
    if not math.isclose(float(empirical_p), exact_current_p, rel_tol=0.0, abs_tol=1e-15):
        raise NullBudgetError("empirical_p disagrees with integer exceedance evidence")

    targets = []
    for alpha_text in alpha_texts:
        alpha = _probability(alpha_text)
        best_case = Decimal(k + 1) / Decimal(maximum_final_budget + 1)
        minimum_budget = _minimum_budget(k, alpha)
        targets.append(
            {
                "alpha": str(alpha),
                "best_case_p_at_budget": str(best_case),
                "required_budget": minimum_budget,
                "status": "FUTILITY_STOPPED" if best_case > alpha else "CONTINUE_ELIGIBLE",
            }
        )

    return {
        "status": "budget_certificate",
        "epistemic_class": "ESTABLISHED",
        "source_null_simulations": n,
        "source_null_exceedances": k,
        "source_empirical_p": exact_current_p,
        "maximum_final_budget": maximum_final_budget,
        "targets": targets,
        "rule": "The final exceedance count cannot be lower than the count already observed.",
        "allowed_claim": "A FUTILITY_STOPPED target is unreachable within this fixed budget even if every remaining null is non-exceeding.",
        "forbidden_claim": "This certificate is not a confidence interval, discovery test, model rejection, or optional-stopping-corrected p-value.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("results/wmap-pilot.json"))
    parser.add_argument("--output", type=Path, default=Path("results/wmap-null-budget.json"))
    parser.add_argument("--maximum-final-budget", type=int, default=1_000_000)
    parser.add_argument("--alpha", action="append", default=None)
    args = parser.parse_args()
    result = json.loads(args.input.read_text())
    certificate = certify_null_budget(
        result,
        args.maximum_final_budget,
        args.alpha or ["0.05", "0.01", "0.001", "0.0000002866515718791933"],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(certificate, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
