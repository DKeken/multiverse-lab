#!/usr/bin/env python3
"""Score SMBHB and phase-transition spectra against NANOGrav free-spectrum KDEs.

GPL-3.0-or-later. Development data only; Planck and polarization stay sealed.
"""

from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from masked_te_injection import ROOT, sha256

CONTRACT_PATH = ROOT / "research" / "gw-kde-discrimination.yml"
ZIP_PATH = ROOT / "data" / "NANOGrav15yr_KDE-FreeSpectra_v1.0.0.zip"
OUTPUT_PATH = ROOT / "results" / "gw-kde-discrimination.json"
VARIANT = "30f_fs{hd}_ceffyl"
H0_SI = 67.5 * 1000.0 / 3.0856775814913673e22
FREF = 3.168e-8


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())

FREF = 3.168e-8


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def load_kde() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        prefix = f"{VARIANT}/"
        freqs = np.load(archive.open(prefix + "freqs.npy"))
        log_pdf = np.load(archive.open(prefix + "density.npy"))[0]
        grid = np.load(archive.open(prefix + "log10rhogrid.npy"))
    return freqs, grid, log_pdf


def omega_smhb(f: np.ndarray, amplitude: float, alpha: float) -> np.ndarray:
    return (2.0 * math.pi**2 / (3.0 * H0_SI**2)) * f**2 * (amplitude * (f / FREF) ** alpha) ** 2


def omega_pt(f: np.ndarray, omega_pk: float, f_pk: float, n2: float, delta: float = 1.0) -> np.ndarray:
    x = f / f_pk
    return omega_pk * x**3 * (1.0 + x ** ((3.0 - n2) / delta)) ** (-delta)


def ceffyl_smhb_sr(f: np.ndarray, amplitude: float, gamma: float, tspan: float) -> np.ndarray:
    fyr = 3.168e-8
    return (amplitude**2 / (12.0 * math.pi**2)) * fyr ** (gamma - 3.0) * f ** (-gamma) / tspan


def score_model(
    log10_rho: np.ndarray,
    grid: np.ndarray,
    log_pdf: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    per_bin_logl = np.empty(log_pdf.shape[0])
    inside_90 = np.empty(log_pdf.shape[0], dtype=int)
    residuals = np.empty(log_pdf.shape[0])
    for index in range(log_pdf.shape[0]):
        weights = np.exp(log_pdf[index] - log_pdf[index].max())
        cdf = np.concatenate(([0.0], np.cumsum((weights[1:] + weights[:-1]) / 2.0 * np.diff(grid))))
        cdf /= cdf[-1]
        point = float(np.clip(log10_rho[index], grid[0], grid[-1]))
        per_bin_logl[index] = float(np.interp(point, grid, log_pdf[index]))
        low = float(grid[np.searchsorted(cdf, 0.05)])
        high = float(grid[np.searchsorted(cdf, 0.95)])
        inside_90[index] = low <= point <= high
        residuals[index] = point - float(np.interp(0.5, cdf, grid))
    return per_bin_logl, inside_90, residuals


def generate() -> dict[str, Any]:
    contract = load_contract()
    freqs, grid, log_pdf = load_kde()
    tspan = 1.0 / float(freqs[1] - freqs[0])

    amplitude, alpha = 2.4e-15, -2.0 / 3.0
    smhb_sr = ceffyl_smhb_sr(freqs, amplitude, 13.0 / 3.0, tspan)
    smhb_log10_rho = 0.5 * np.log10(smhb_sr)
    smhb_logl, smhb_inside, smhb_residuals = score_model(smhb_log10_rho, grid, log_pdf)

    omega_smhb_published = omega_smhb(freqs, amplitude, alpha)

    rows: list[dict[str, Any]] = []
    for omega_pk in (1e-11, 1e-10, 1e-9, 1e-8, 1e-7):
        for log_fpk in range(-9, -6):
            f_pk = 10.0 ** log_fpk
            for n2 in (-1.0, 0.0, 1.0):
                pt_ratio = omega_pt(freqs, omega_pk, f_pk, n2) / omega_smhb_published
                pt_log10_rho = 0.5 * np.log10(smhb_sr * pt_ratio)
                if not np.all(np.isfinite(pt_log10_rho)):
                    continue
                pt_logl, pt_inside, pt_residuals = score_model(pt_log10_rho, grid, log_pdf)
                delta_logl = float(np.sum(pt_logl) - np.sum(smhb_logl))
                rows.append(
                    {
                        "omega_pk": omega_pk,
                        "f_pk_hz": f_pk,
                        "n2": n2,
                        "delta_logl_vs_smhb": delta_logl,
                        "median_dex_residual": float(np.median(pt_residuals)),
                        "bins_inside_90pct": int(pt_inside.sum()),
                        "rejected_outside_support": int(np.count_nonzero(pt_logl <= math.log(1e-300))) > 6,
                        "pt_preferred": bool(delta_logl > 0 and pt_inside.sum() >= 20),
                    }
                )

    preferred = [row for row in rows if row["pt_preferred"]]
    smhb_selfcheck_bins = int(smhb_inside.sum())
    checks = {
        "smhb_selfcheck": smhb_selfcheck_bins >= 20,
        "finite_scores": bool(np.all(np.isfinite(smhb_logl))),
    }
    return {
        "experiment_id": contract["experiment_id"],
        "status": "PT-PREFERRED" if preferred else "SMBHB-PREFERRED",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "registry_id": contract["data"]["registry_id"],
            "archive_sha256": sha256(ZIP_PATH),
        },
        "provenance": {
            "variant": VARIANT,
            "bin_count": int(freqs.size),
            "frequency_min_hz": float(freqs[0]),
            "frequency_max_hz": float(freqs[-1]),
            "kde_grid_points": int(grid.size),
            "observational_cmb_maps_opened": False,
            "planck_accessed": False,
            "polarization_accessed": False,
        },
        "smhb_baseline": {
            "amplitude": amplitude,
            "alpha": alpha,
            "per_bin_z_like_logl": [float(value) for value in smhb_logl],
            "median_dex_residual": float(np.median(smhb_residuals)),
            "bins_inside_90pct": smhb_selfcheck_bins,
        },
        "decision_rule": contract["decision_rule"],
        "grid_size": len(rows),
        "pt_preferred_count": len(preferred),
        "best_pt_point": max(rows, key=lambda row: row["delta_logl_vs_smhb"]),
        "grid": rows,
        "checks": checks,
        "limitations": [
            "Per-bin KDE marginals ignore inter-bin correlations; the combined log-density is a screening statistic, not a model evidence.",
            "The rho-to-Omega convention follows the Ceffyl free-spectrum labels and was verified only against the labels file.",
            "Closed-form PT templates are our feasibility family; the published pt_bubble MCMC chains remain in the declared 22.4 GB archive.",
            "No Planck product or observational polarization was accessed.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {key: result[key] for key in ("experiment_id", "status", "smhb_baseline", "pt_preferred_count", "best_pt_point", "checks")},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
