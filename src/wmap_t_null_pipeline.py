#!/usr/bin/env python3
"""Calibrate the WMAP-T multi-radius filter against an end-to-end null pipeline.

GPL-3.0-or-later. Development data only; Planck and polarization stay sealed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import healpy as hp
import numpy as np
import yaml

from bubble_te_template import RADIAL_NODES, basis_template, transfer_data
from masked_te_injection import ROOT, sha256

CONTRACT_PATH = ROOT / "research" / "wmap-t-null-pipeline.yml"
MAP_PATH = ROOT / "data" / "wmap_ilc_9yr_v5.fits"
OUTPUT_PATH = ROOT / "results" / "wmap-t-null-pipeline.json"
UPPER_LIMIT_95 = 1.6448536269514722


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def galactic_mask(nside: int, minimum_latitude_deg: float) -> np.ndarray:
    theta, _ = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    latitude = 90.0 - np.degrees(theta)
    return (np.abs(latitude) >= minimum_latitude_deg).astype(float)


def radius_scores(
    alms: np.ndarray,
    templates: list[np.ndarray],
    inverse: np.ndarray,
    ell_of_alm: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    z_scores = np.empty(len(templates))
    amplitudes = np.empty(len(templates))
    for index, template in enumerate(templates):
        s = float(np.sum(inverse * np.real(alms * np.conjugate(template))))
        v = float(np.sum(inverse * np.square(np.abs(template))))
        amplitudes[index] = s / v
        z_scores[index] = amplitudes[index] * np.sqrt(v)
    return z_scores, amplitudes


def generate() -> dict[str, Any]:
    contract = load_contract()
    pipeline = contract["pipeline"]
    statistic = contract["statistic"]
    nside = int(pipeline["nside_analysis"])
    lmax = int(pipeline["lmax"])
    radii = [float(value) for value in pipeline["angular_radii_deg"]]
    minimum_latitude = float(pipeline["mask"].split("|b| < ")[1].split(" ")[0])

    data, transfer = transfer_data()
    derived = data.get_derived_params()
    x_ls = float(data.comoving_radial_distance(derived["zstar"]))
    c_tt = data.get_unlensed_scalar_cls(lmax=lmax, raw_cl=True)[:, 0].copy()
    c_tt[:2] = 0.0

    map_native = np.asarray(hp.read_map(str(MAP_PATH), field=0), dtype=float)
    map_dimless = hp.ud_grade(map_native / 2725.5, nside) if hp.get_nside(map_native) != nside else map_native / 2725.5
    mask = galactic_mask(nside, minimum_latitude)
    data_alms = hp.map2alm(map_dimless * mask, lmax=lmax, iter=0)

    ell_of_alm = hp.Alm.getlm(lmax)[0]
    inverse = np.where(ell_of_alm >= 2, 1.0 / np.where(c_tt[ell_of_alm] > 0, c_tt[ell_of_alm], 1.0), 0.0)
    templates: list[np.ndarray] = []
    for radius_deg in radii:
        x_c = x_ls * np.cos(np.radians(radius_deg))
        template = basis_template(transfer, float(x_c), x_ls, 1, RADIAL_NODES)
        t_alm = np.zeros(hp.Alm.getsize(lmax), dtype=np.complex128)
        ell_values = np.asarray(template["ell"], dtype=int)
        t_alm[hp.Alm.getidx(lmax, ell_values, 0)] = np.asarray(template["temperature_bl0"])
        templates.append(t_alm)

    data_z, data_a = radius_scores(data_alms, templates, inverse, ell_of_alm)
    observed_max = float(np.max(data_z))

    null_count = int(statistic["null_simulations"])
    seed_start = int(statistic["null_seed_start"])
    generator = np.random.default_rng(seed_start)
    null_max = np.empty(null_count)
    null_amplitudes = np.empty((null_count, len(radii)))
    for index in range(null_count):
        cmb_alm = hp.synalm(c_tt, lmax=lmax, new=True)
        cmb_map = hp.alm2map(cmb_alm, nside, lmax=lmax)
        null_alms = hp.map2alm(cmb_map * mask, lmax=lmax, iter=0)
        z_scores, amplitudes = radius_scores(null_alms, templates, inverse, ell_of_alm)
        null_max[index] = np.max(z_scores)
        null_amplitudes[index] = amplitudes

    exceedances = int(np.count_nonzero(null_max >= observed_max))
    p_value = (1 + exceedances) / (1 + null_count)
    empirical_sigma = np.std(null_amplitudes, axis=0, ddof=1)
    upper_limits = UPPER_LIMIT_95 * empirical_sigma
    rows = [
        {
            "angular_radius_deg": radii[index],
            "data_amplitude_R0": float(data_a[index]),
            "data_z": float(data_z[index]),
            "empirical_amplitude_sigma": float(empirical_sigma[index]),
            "upper_limit_95_R0": float(upper_limits[index]),
            "typical_physical_R0": 0.179 * 0.1 * 1.0 * ((x_ls - x_ls * np.cos(np.radians(radii[index]))) / x_ls),
        }
        for index in range(len(radii))
    ]
    finite = bool(np.all(np.isfinite(null_max)) and np.all(np.isfinite(data_z)))
    return {
        "experiment_id": contract["experiment_id"],
        "status": "DETECTION" if p_value <= 0.0027 else "NO-DETECTION",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "screen_result_sha256": sha256(ROOT / contract["inherit"]["screen_result"]),
        },
        "provenance": {
            "map_path": str(MAP_PATH.relative_to(ROOT)),
            "map_sha256": sha256(MAP_PATH),
            "nside_analysis": nside,
            "sky_fraction_used": float(np.mean(mask)),
            "null_count": null_count,
            "null_seed_start": seed_start,
            "observational_cmb_maps_opened": True,
            "development_data_only": True,
            "planck_accessed": False,
            "polarization_accessed": False,
        },
        "observed": {
            "per_radius": rows,
            "max_z": observed_max,
            "null_max_mean": float(np.mean(null_max)),
            "null_max_std": float(np.std(null_max, ddof=1)),
            "null_max_maximum": float(np.max(null_max)),
            "exceedances": exceedances,
            "p_value": p_value,
        },
        "checks": {
            "finite_scores": finite,
            "detection": p_value <= 0.0027,
        },
        "limitations": [
            "Nulls are pure Gaussian CMB skies; ILC residual noise and foreground residuals are not simulated.",
            "Zero-iteration transforms are applied identically to data and nulls, making calibration internally exact for this pipeline definition.",
            "The ud_grade to nside 256 is part of the frozen pipeline and differs from the nside-512 screen; this gate supersedes analytic screen thresholds.",
            "No Planck product or observational polarization was accessed.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "observed", "checks")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
