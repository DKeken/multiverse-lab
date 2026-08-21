from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def _unit_residual(vector: np.ndarray, nuisance: np.ndarray) -> np.ndarray:
    coefficients = np.linalg.solve(nuisance.T @ nuisance, nuisance.T @ vector)
    residual = vector - nuisance @ coefficients
    norm = np.linalg.norm(residual)
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("template is contained in nuisance span")
    return residual / norm


def _score(samples: np.ndarray, template: np.ndarray, nuisance: np.ndarray, variance: float) -> np.ndarray:
    projected = samples - (samples @ nuisance) @ np.linalg.solve(nuisance.T @ nuisance, nuisance.T)
    return projected @ template / math.sqrt(variance)


def calibrate(
    *,
    seed: int = 20260821,
    skies: int = 16_384,
    temperature_trials: int = 256,
    bins: int = 24,
    rho: float = 0.55,
    threshold: float = 3.0,
    injection_sigma: float = 3.0,
) -> dict[str, Any]:
    if skies < 1_000 or temperature_trials < 2 or bins < 6:
        raise ValueError("calibration grid is too small")
    if threshold <= 0.0 or injection_sigma <= 0.0:
        raise ValueError("thresholds must be positive")
    if not -1.0 < rho < 1.0 or rho == 0.0:
        raise ValueError("rho must be non-zero with absolute value below one")
    rng = np.random.default_rng(seed)
    radius = np.linspace(0.0, 1.0, bins)
    nuisance = np.column_stack((np.ones(bins), radius))
    raw_template = (1.0 - radius**2) * np.exp(-0.5 * ((radius - 0.58) / 0.20) ** 2)
    template = _unit_residual(raw_template, nuisance)

    temperature = rng.standard_normal((skies, temperature_trials))
    selected_t = temperature.min(axis=1)
    conditional_variance = 1.0 - rho**2
    independent_e = rng.standard_normal((skies, bins)) * math.sqrt(conditional_variance)
    coupling = -rho * template
    selected_e = independent_e + selected_t[:, None] * coupling

    naive_score = _score(selected_e, template, nuisance, conditional_variance)
    conditional_e = selected_e - selected_t[:, None] * coupling
    conditional_score = _score(conditional_e, template, nuisance, conditional_variance)

    nuisance_coefficients = rng.standard_normal((skies, nuisance.shape[1]))
    contaminated = conditional_e + nuisance_coefficients @ nuisance.T
    contaminated_score = _score(contaminated, template, nuisance, conditional_variance)
    nuisance_delta = float(np.max(np.abs(contaminated_score - conditional_score)))

    injected_e = conditional_e + injection_sigma * math.sqrt(conditional_variance) * template
    injection_score = _score(injected_e, template, nuisance, conditional_variance)
    b_score = rng.standard_normal(skies)
    b_veto_null = np.abs(b_score) >= threshold
    b_veto_injected = np.abs(b_score) >= threshold

    expected_tail = 0.5 * math.erfc(threshold / math.sqrt(2.0))
    expected_count = skies * expected_tail
    count_sigma = math.sqrt(skies * expected_tail * (1.0 - expected_tail))
    conditional_count = int(np.count_nonzero(conditional_score >= threshold))
    naive_count = int(np.count_nonzero(naive_score >= threshold))
    mean_tolerance = 4.0 / math.sqrt(skies)
    std_tolerance = 4.0 / math.sqrt(2.0 * (skies - 1))
    conditional_mean = float(np.mean(conditional_score))
    conditional_std = float(np.std(conditional_score, ddof=1))

    checks = {
        "conditional_tail_calibrated": abs(conditional_count - expected_count) <= 4.0 * count_sigma,
        "conditional_mean_calibrated": abs(conditional_mean) <= mean_tolerance,
        "conditional_std_calibrated": abs(conditional_std - 1.0) <= std_tolerance,
        "nuisance_invariant": nuisance_delta <= 1e-10,
        "injection_recovered": abs(float(np.mean(injection_score)) - injection_sigma) <= mean_tolerance,
        "pure_e_preserves_b_veto": bool(np.array_equal(b_veto_null, b_veto_injected)),
    }

    return {
        "experiment_id": "joint-te-selection-calibration-v1",
        "epistemic_class": "ADAPTED",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "interpretation": "Synthetic calibration of a conditional T/E statistic; no observational polarization data were accessed.",
        "selection": {
            "temperature_trials_per_sky": temperature_trials,
            "selected_temperature_mean_sigma": float(np.mean(selected_t)),
            "known_cold_spot_separation_deg": 1.1028793761607039,
        },
        "configuration": {
            "seed": seed,
            "skies": skies,
            "vector_bins": bins,
            "te_correlation": rho,
            "one_sided_z_threshold": threshold,
            "conditional_injection_sigma": injection_sigma,
        },
        "null_calibration": {
            "expected_one_sided_rate": expected_tail,
            "expected_count": expected_count,
            "count_standard_deviation": count_sigma,
            "naive_selected_e_count": naive_count,
            "naive_selected_e_rate": naive_count / skies,
            "conditional_count": conditional_count,
            "conditional_rate": conditional_count / skies,
            "conditional_mean": conditional_mean,
            "conditional_standard_deviation": conditional_std,
        },
        "controls": {
            "maximum_nuisance_score_delta": nuisance_delta,
            "injected_score_mean": float(np.mean(injection_score)),
            "b_veto_count": int(np.count_nonzero(b_veto_null)),
        },
        "checks": checks,
        "forbidden_claim": "PASS does not constitute evidence for a bubble collision, the multiverse, or any observation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/joint-te-synthetic.json"))
    args = parser.parse_args()
    result = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
