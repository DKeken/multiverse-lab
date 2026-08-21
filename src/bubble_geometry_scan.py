#!/usr/bin/env python3
"""Survey bubble-collision angular radii for physical detectability ceilings.

GPL-3.0-or-later. Cosmic-variance Fisher forecast only; no observational maps.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml

from bubble_te_template import (
    COSMOLOGY,
    RADIAL_NODES,
    basis_template,
    fisher_information,
    transfer_data,
)
from masked_te_injection import ROOT, sha256

CONTRACT_PATH = ROOT / "research" / "bubble-geometry-scan.yml"
OUTPUT_PATH = ROOT / "results" / "bubble-geometry-scan.json"


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def generate() -> dict[str, Any]:
    contract = load_contract()
    survey = contract["survey"]
    lmax = int(survey["lmax"])
    data, transfer = transfer_data()
    derived = data.get_derived_params()
    x_ls = float(data.comoving_radial_distance(derived["zstar"]))

    basis_power = {"linear": 1, "quadratic": 2}[str(survey["basis"])]
    rows: list[dict[str, float | int | bool]] = []
    for radius_deg in survey["angular_radii_deg"]:
        radius_deg = float(radius_deg)
        x_c = x_ls * math.cos(math.radians(radius_deg))
        template = basis_template(transfer, x_c, x_ls, basis_power, RADIAL_NODES)
        fisher = fisher_information(data, {"linear": template})
        sigma = float(fisher["per_basis"]["linear"]["joint_unit_amplitude_sigma"])
        ratio = (x_ls - x_c) / x_ls
        fiducial_r0 = (
            float(survey["fiducial_constants"]["A"])
            * float(survey["fiducial_constants"]["delta_phi_0_over_Mpl"])
            * float(survey["fiducial_constants"]["separation_factor_s"])
            * ratio
        )
        typical_r0 = (
            float(survey["typical_constants"]["A"])
            * float(survey["typical_constants"]["delta_phi_0_over_Mpl"])
            * float(survey["typical_constants"]["separation_factor_s"])
            * ratio
        )
        rows.append(
            {
                "angular_radius_deg": radius_deg,
                "causal_boundary_mpc": x_c,
                "shell_ratio": ratio,
                "joint_linear_sigma": sigma,
                "fiducial_maximum_R0": fiducial_r0,
                "typical_R0": typical_r0,
                "fiducial_ceiling_sigma": fiducial_r0 / sigma,
                "typical_ceiling_sigma": typical_r0 / sigma,
                "viable": fiducial_r0 / sigma >= 3.0,
            }
        )

    viable = [row["angular_radius_deg"] for row in rows if row["viable"]]
    return {
        "experiment_id": contract["experiment_id"],
        "status": "SURVEY-COMPLETE",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
        },
        "provenance": {
            "template_producer": "src/bubble_te_template.py",
            "amplitude_mapping": "research/bubble-amplitude-prior.yml",
            "camb_cosmology": COSMOLOGY,
            "lmax": lmax,
            "radial_nodes": RADIAL_NODES,
            "observational_cmb_maps_opened": False,
            "planck_accessed": False,
        },
        "last_scattering_distance_mpc": x_ls,
        "viability_rule": contract["viability_rule"],
        "viable_radii_deg": viable,
        "radii": rows,
        "limitations": [
            "Cosmic-variance full-sky Fisher only; mask, beam, noise, and foregrounds can only lower these ceilings.",
            "Ell truncation at 256 excludes sharp-rim multipoles, so every ceiling here is a lower bound.",
            "The scan is center-independent because full-sky harmonic Fisher does not depend on collision position.",
            "A forecast ceiling is not observational evidence and does not access any holdout product.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "viable_radii_deg", "radii")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
