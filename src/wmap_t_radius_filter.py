#!/usr/bin/env python3
"""Screen development WMAP ILC temperature for multi-radius bubble templates.

GPL-3.0-or-later. Development data only; Planck and polarization stay sealed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import healpy as hp
import numpy as np
import yaml

from bubble_te_template import RADIAL_NODES, basis_template, transfer_data
from masked_te_injection import ROOT, sha256

CONTRACT_PATH = ROOT / "research" / "wmap-t-radius-filter.yml"
MAP_PATH = ROOT / "data" / "wmap_ilc_9yr_v5.fits"
OUTPUT_PATH = ROOT / "results" / "wmap-t-radius-filter.json"


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def masked_alms(map_dimless: np.ndarray, mask: np.ndarray, lmax: int) -> np.ndarray:
    return hp.map2alm(np.asarray(map_dimless) * mask, lmax=lmax)

def score(alms: np.ndarray, template: np.ndarray, c_tt: np.ndarray, lmax: int) -> tuple[float, float]:
    ell_of_alm = hp.Alm.getlm(lmax)[0]
    inverse = np.zeros_like(c_tt)
    positive = c_tt > 0
    inverse[positive] = 1.0 / c_tt[positive]
    weight = np.where(ell_of_alm >= 2, inverse[ell_of_alm], 0.0)
    s = float(np.sum(weight * np.real(alms * np.conjugate(template))))
    v = float(np.sum(weight * np.square(np.abs(template))))
    if v <= 0:
        raise RuntimeError("Template self-information must be positive")
    return s, v


def generate() -> dict[str, Any]:
    contract = load_contract()
    analysis = contract["analysis"]
    lmax = int(analysis["lmax"])
    map_mk = hp.read_map(str(MAP_PATH), field=0)
    nside = hp.get_nside(map_mk)
    map_dimless = np.asarray(map_mk, dtype=float) / 2725.5
    theta, phi = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    latitude = 90.0 - np.degrees(theta)
    mask = (np.abs(latitude) >= float(analysis["mask"].split("|b| < ")[1].split(" ")[0])).astype(float)
    f_sky = float(np.mean(mask))

    data, transfer = transfer_data()
    derived = data.get_derived_params()
    x_ls = float(data.comoving_radial_distance(derived["zstar"]))
    scalar_cls = data.get_unlensed_scalar_cls(lmax=lmax, raw_cl=True)
    c_tt = scalar_cls[:, 0]
    alms = masked_alms(map_dimless, mask, lmax)

    rows: list[dict[str, float | int]] = []
    for radius_deg in analysis["angular_radii_deg"]:
        radius_deg = float(radius_deg)
        x_c = x_ls * math.cos(math.radians(radius_deg))
        template = basis_template(transfer, x_c, x_ls, 1, RADIAL_NODES)
        t_alm = np.zeros(hp.Alm.getsize(lmax), dtype=np.complex128)
        ell_values = np.asarray(template["ell"], dtype=int)
        t_alm[hp.Alm.getidx(lmax, ell_values, 0)] = np.asarray(template["temperature_bl0"])
        s, v = score(alms, t_alm, c_tt, lmax)
        a_hat = s / v
        z_pre = a_hat * math.sqrt(v)
        theta_rad = math.radians(radius_deg)
        n_eff = max(f_sky * 4.0 * math.pi / (2.0 * math.pi * theta_rad**2), 2.0)
        trials_penalty = math.sqrt(2.0 * math.log(n_eff))
        z_post = z_pre - trials_penalty
        upper95_pre = 1.6448536269514722 / math.sqrt(v)
        rows.append(
            {
                "angular_radius_deg": radius_deg,
                "amplitude_hat_R0": a_hat,
                "pre_trials_z": z_pre,
                "effective_positions": n_eff,
                "trials_penalty_sigma": trials_penalty,
                "post_trials_z": z_post,
                "upper_limit_95_R0": upper95_pre,
                "typical_physical_R0": 0.179 * 0.1 * 1.0 * ((x_ls - x_c) / x_ls),
            }
        )

    detections = [row for row in rows if row["post_trials_z"] >= 3.0]
    return {
        "experiment_id": contract["experiment_id"],
        "status": "DETECTION" if detections else "NO-DETECTION",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
        },
        "provenance": {
            "map_path": str(MAP_PATH.relative_to(ROOT)),
            "map_sha256": sha256(MAP_PATH),
            "nside": int(nside),
            "sky_fraction_used": f_sky,
            "observational_cmb_maps_opened": True,
            "development_data_only": True,
            "planck_accessed": False,
            "polarization_accessed": False,
        },
        "radii": rows,
        "checks": {
            "finite_scores": all(math.isfinite(row["pre_trials_z"]) for row in rows),
            "detection": bool(detections),
        },
        "limitations": [
            "Pseudo-Cl masked alms ignore mode coupling; this is screening, not a final analysis.",
            "ILC residual noise and foreground residuals are neglected under the cosmic-variance assumption.",
            "Trials correction uses an independent-lobe approximation, not an end-to-end null pipeline.",
            "Any interesting excess must survive a frozen end-to-end null pipeline before promotion language.",
            "No Planck product or observational polarization was accessed.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "provenance", "radii", "checks")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
