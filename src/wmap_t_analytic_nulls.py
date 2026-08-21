#!/usr/bin/env python3
"""Exact analytic null distribution for the multi-radius WMAP-T matched filter.

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
from scipy.stats import multivariate_normal

from bubble_te_template import RADIAL_NODES, basis_template, transfer_data
from masked_te_injection import ROOT, sha256

CONTRACT_PATH = ROOT / "research" / "wmap-t-analytic-nulls.yml"
MAP_PATH = ROOT / "data" / "wmap_ilc_9yr_v5.fits"
PIPELINE_RESULT_PATH = ROOT / "results" / "wmap-t-null-pipeline.json"
OUTPUT_PATH = ROOT / "results" / "wmap-t-analytic-nulls.json"
GL_NODES = 1200
LEGENDRE_SUMS = (1600, 800)
UPPER_LIMIT_95 = 1.6448536269514722


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def build_templates(
    radii: list[float], x_ls: float, transfer: Any, lmax: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return (harmonic m=0 alm vector, dimensionless m=0 coefficient array) per radius."""
    templates: list[tuple[np.ndarray, np.ndarray]] = []
    for radius_deg in radii:
        x_c = x_ls * math.cos(math.radians(radius_deg))
        template = basis_template(transfer, float(x_c), x_ls, 1, RADIAL_NODES)
        ell_values = np.asarray(template["ell"], dtype=int)
        values = np.asarray(template["temperature_bl0"])
        t_alm = np.zeros(hp.Alm.getsize(lmax), dtype=np.complex128)
        t_alm[hp.Alm.getidx(lmax, ell_values, 0)] = values
        m_zero = np.zeros(lmax + 1)
        m_zero[ell_values] = values
        templates.append((t_alm, m_zero))
    return templates


def masked_kernel_moments(
    m_zero: np.ndarray,
    c_tt: np.ndarray,
    mask_mu: np.ndarray,
    nodes: np.ndarray,
    node_weights: np.ndarray,
    l_sums: int,
) -> np.ndarray:
    orders = np.arange(l_sums + 1)
    legendre = np.polynomial.legendre.legvander(nodes, l_sums).T  # (l_sums+1, GL_NODES)
    coefficients = np.zeros(len(c_tt))
    coefficients[: len(m_zero)] = m_zero
    positive = c_tt > 0
    coefficients[positive] /= c_tt[positive]
    coefficients[:2] = 0.0
    normalization = np.sqrt((2 * np.arange(len(c_tt)) + 1) / (4 * math.pi))
    kernel = (coefficients * normalization) @ legendre[: len(c_tt)]
    masked_kernel = kernel * mask_mu
    return ((2 * orders + 1) / 2.0) * (legendre @ (node_weights * masked_kernel))


def generate() -> dict[str, Any]:
    contract = load_contract()
    pipeline = yaml.safe_load((ROOT / contract["inherit"]["pipeline_contract"]).read_text())["pipeline"]
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
    map_dimless = hp.ud_grade(map_native / 2725.5, nside)
    theta, _ = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    mask = (np.abs(90.0 - np.degrees(theta)) >= minimum_latitude).astype(float)
    data_alms = hp.map2alm(map_dimless * mask, lmax=lmax, iter=0)

    templates = build_templates(radii, x_ls, transfer, lmax)
    alm_vectors = [pair[0] for pair in templates]
    m_zero_vectors = [pair[1] for pair in templates]

    base_contract = yaml.safe_load((ROOT / contract["inherit"]["pipeline_contract"]).read_text())
    seed_start = int(base_contract["statistic"]["null_seed_start"])
    ell_of_alm = hp.Alm.getlm(lmax)[0]
    inverse = np.where(
        ell_of_alm >= 2,
        1.0 / np.where(c_tt[ell_of_alm] > 0, c_tt[ell_of_alm], 1.0),
        0.0,
    )
    self_information = np.array(
        [float(np.sum(inverse * np.square(np.abs(t)))) for t in alm_vectors]
    )
    data_z = (
        np.array(
            [float(np.sum(inverse * np.real(data_alms * np.conjugate(t)))) for t in alm_vectors]
        )
        / np.sqrt(self_information)
    )

    nodes, node_weights = np.polynomial.legendre.leggauss(GL_NODES)
    cut_cosine = math.sin(math.radians(minimum_latitude))
    mask_mu = (np.abs(nodes) >= abs(cut_cosine)).astype(float)

    moment_blocks: dict[int, list[np.ndarray]] = {sums: [] for sums in LEGENDRE_SUMS}
    for m_zero in m_zero_vectors:
        for sums in LEGENDRE_SUMS:
            moment_blocks[sums].append(
                masked_kernel_moments(m_zero, c_tt, mask_mu, nodes, node_weights, sums)
            )

    covariance = np.empty((len(radii), len(radii)))
    truncation_delta = 0.0
    for row in range(len(radii)):
        for column in range(len(radii)):
            block_values = []
            for sums in LEGENDRE_SUMS:
                moments_row = moment_blocks[sums][row]
                shared = min(moments_row.size, len(c_tt))
                orders = np.arange(2, shared)
                pixel_window = np.asarray(hp.pixwin(nside, lmax=shared - 1))
                total = np.sum(
                    c_tt[2:shared]
                    * pixel_window[2:shared] ** 2
                    * moments_row[2:shared]
                    * moment_blocks[sums][column][2:shared]
                    / (2 * orders + 1)
                )
                block_values.append(4.0 * math.pi * total)
            covariance[row, column] = block_values[0]
            if row == column:
                truncation_delta = max(
                    truncation_delta,
                    abs(block_values[0] - block_values[1]) / abs(block_values[0]),
                )
    if truncation_delta > 1e-6:
        raise RuntimeError("Legendre truncation is unstable at the frozen tolerance")

    analytic_amplitude_sigma = np.sqrt(1.0 / np.diag(covariance))
    z_correlation = covariance / np.sqrt(np.outer(np.diag(covariance), np.diag(covariance)))

    published = json.loads(PIPELINE_RESULT_PATH.read_text())
    empirical_sigma = np.array(
        [row["empirical_amplitude_sigma"] for row in published["observed"]["per_radius"]]
    )
    diagonal_ratios = analytic_amplitude_sigma / empirical_sigma

    validation_count = 800
    generator = np.random.default_rng(seed_start - 1)
    null_scores = np.empty((validation_count, len(radii)))
    for index in range(validation_count):
        cmb_alm = hp.synalm(c_tt, lmax=lmax, new=True)
        cmb_map = hp.alm2map(cmb_alm, nside, lmax=lmax)
        null_alms = hp.map2alm(cmb_map * mask, lmax=lmax, iter=0)
        null_scores[index] = [
            float(np.sum(inverse * np.real(null_alms * np.conjugate(t)))) for t in alm_vectors
        ]
    empirical_covariance = np.cov(null_scores, rowvar=False, ddof=1)
    empirical_correlation = empirical_covariance / np.sqrt(
        np.outer(np.diag(empirical_covariance), np.diag(empirical_covariance))
    )
    offdiagonal_mask = ~np.eye(len(radii), dtype=bool)
    offdiagonal_delta = float(
        np.max(np.abs(z_correlation - empirical_correlation)[offdiagonal_mask])
    )

    observed_max = float(np.max(data_z))
    scaled_threshold = observed_max
    analytic_p_value = float(
        1.0
        - multivariate_normal(
            mean=np.zeros(len(radii)), cov=z_correlation, allow_singular=False
        ).cdf(np.full(len(radii), scaled_threshold))
    )

    checks = {
        "diagonal_within_5pct": bool(np.all(np.abs(diagonal_ratios - 1.0) <= 0.05)),
        "offdiagonal_within_0p08": offdiagonal_delta <= 0.08,
        "truncation_stable": bool(truncation_delta <= 1e-6),
    }
    return {
        "experiment_id": contract["experiment_id"],
        "status": "VALIDATED" if all(checks.values()) else "INVALID",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "pipeline_result_sha256": sha256(PIPELINE_RESULT_PATH),
        },
        "provenance": {
            "map_path": str(MAP_PATH.relative_to(ROOT)),
            "map_sha256": sha256(MAP_PATH),
            "nside_analysis": nside,
            "gauss_legendre_nodes": GL_NODES,
            "legendre_sums": list(LEGENDRE_SUMS),
            "validation_null_count": validation_count,
            "observational_cmb_maps_opened": True,
            "development_data_only": True,
            "planck_accessed": False,
            "polarization_accessed": False,
        },
        "analytic": {
            "per_radius": [
                {
                    "angular_radius_deg": radii[index],
                    "data_z": float(data_z[index]),
                    "analytic_amplitude_sigma": float(analytic_amplitude_sigma[index]),
                    "published_empirical_sigma": float(empirical_sigma[index]),
                    "sigma_ratio": float(diagonal_ratios[index]),
                    "upper_limit_95_R0": UPPER_LIMIT_95 * float(analytic_amplitude_sigma[index]),
                }
                for index in range(len(radii))
            ],
            "z_correlation_matrix": z_correlation.tolist(),
            "observed_max_z": observed_max,
            "analytic_p_value": analytic_p_value,
            "published_empirical_p_value": published["observed"]["p_value"],
        },
        "validation": {
            "truncation_relative_delta": float(truncation_delta),
            "offdiagonal_max_abs_delta": offdiagonal_delta,
            "fresh_null_empirical_correlation": empirical_correlation.tolist(),
        },
        "checks": checks,
        "limitations": [
            "Exact only for the linear Gaussian pipeline; non-Gaussian ILC residual tests still require simulations.",
            "Legendre moments truncated at 1600 with an 800-term stability check at the frozen tolerance.",
            "The 200 fresh nulls validate the covariance and do not replace the closed-form calibration.",
            "No Planck product or observational polarization was accessed.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {key: result[key] for key in ("experiment_id", "status", "analytic", "validation", "checks")},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
