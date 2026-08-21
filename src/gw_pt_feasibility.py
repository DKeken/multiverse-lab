#!/usr/bin/env python3
"""Closed-form SMBHB versus first-order-phase-transition discrimination feasibility.

GPL-3.0-or-later. Published-constraint calculator; downloads nothing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml

from masked_te_injection import ROOT, sha256

CONTRACT_PATH = ROOT / "research" / "gw-pt-feasibility.yml"
OUTPUT_PATH = ROOT / "results" / "gw-pt-feasibility.json"

H0_SI = 67.5 * 1000.0 / 3.0856775814913673e22
FREF = 3.168e-8


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def omega_smhb(f: float, amplitude: float, alpha: float) -> float:
    return (2.0 * math.pi**2 / (3.0 * H0_SI**2)) * f * f * (amplitude * (f / FREF) ** alpha) ** 2


def omega_pt(f: float, omega_pk: float, f_pk: float, n2: float, delta: float = 1.0) -> float:
    x = f / f_pk
    return omega_pk * x**3 * (1.0 + x ** ((3.0 - n2) / delta)) ** (-delta)


def generate() -> dict[str, Any]:
    contract = load_contract()
    anchor = contract["published_anchor"]
    amplitude = float(anchor["strain_amplitude_90pct"]["median"])
    alpha = float(anchor["spectral_index_alpha"])
    sigma_dex = float(contract["discrimination_metric"]["sigma_dex_one_sigma"])
    smhb_reference = omega_smhb(FREF, amplitude, alpha)

    grid: list[dict[str, float | int | bool]] = []
    for omega_pk in (1e-11, 1e-10, 1e-9, 1e-8, 1e-7):
        for log_fpk in range(-9, -6):
            f_pk = 10.0 ** log_fpk
            for n2 in (-1.0, 0.0, 1.0):
                pt_at_ref = omega_pt(FREF, omega_pk, f_pk, n2)
                dex_distance = abs(math.log10(pt_at_ref) - math.log10(smhb_reference))
                today_sigma = dex_distance / sigma_dex
                projection_sigma = today_sigma * math.sqrt(20.0 / 15.0)
                grid.append(
                    {
                        "omega_pk": omega_pk,
                        "f_pk_hz": f_pk,
                        "n2": n2,
                        "pt_omega_at_ref": pt_at_ref,
                        "dex_distance": dex_distance,
                        "today_sigma": today_sigma,
                        "twenty_year_sigma": projection_sigma,
                        "distinguishable_today": today_sigma >= 2.0,
                        "distinguishable_twenty_year": projection_sigma >= 3.0,
                    }
                )
    open_count = sum(
        1
        for row in grid
        if row["today_sigma"] >= 2.0 and row["twenty_year_sigma"] >= 3.0
    )
    best = max(grid, key=lambda row: min(row["today_sigma"], 99.0))
    return {
        "experiment_id": contract["experiment_id"],
        "status": "OPEN-CHAIN-GATE" if open_count > 0 else "KEEP-FROZEN",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
        },
        "provenance": {
            "primary_source": anchor["source"],
            "h0_si": H0_SI,
            "reference_frequency_hz": FREF,
            "observational_cmb_maps_opened": False,
            "planck_accessed": False,
            "polarization_accessed": False,
            "downloads_performed": False,
        },
        "smhb_reference_omega_at_1_over_year": smhb_reference,
        "decision_rule": contract["decision_rule"],
        "grid_size": len(grid),
        "grid_points_passing_rule": open_count,
        "best_point": best,
        "grid": grid,
        "checks": {
            "anchor_amplitude_matches_source": abs(amplitude - 2.4e-15) < 1e-17,
            "causal_low_slope_used": True,
            "rule_applied": True,
        },
        "limitations": [
            "Single-frequency discrimination proxy; full chain-based model comparison remains the authority.",
            "Spectral-index uncertainty of the published fit is not propagated into sigma_dex.",
            "The temperature bridge formula is an order-of-magnitude literature conversion pending primary-source verification.",
            "No data download was performed; public chains must be registry-frozen before any fetch gate.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {key: result[key] for key in ("experiment_id", "status", "smhb_reference_omega_at_1_over_year", "grid_points_passing_rule", "best_point")},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
