#!/usr/bin/env python3
"""Validate frozen T/E depth with matrix-free anisotropic pixel covariance.

GPL-3.0-or-later. Synthetic cut-sky maps only; no observational products.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import healpy as hp
import numpy as np
import pymaster as nmt
import pysm3
import yaml
from scipy.sparse.linalg import LinearOperator, cg

from masked_te_injection import (
    CMB_TEMPERATURE_UK,
    ROOT,
    harmonic_dot,
    cmb_covariance,
    generate_foregrounds,
    make_mask,
    physical_alms,
    sha256,
)
from te_noise_depth import CONTRACT_PATH as DEPTH_CONTRACT_PATH
from te_systematics_stress import (
    BASE_CONTRACT_PATH,
    CONTRACT_PATH as STRESS_CONTRACT_PATH,
    beam_qu_maps,
    beam_window,
    load_contracts,
    rotate_and_gain,
)

CONTRACT_PATH = ROOT / "research" / "te-pixel-covariance.yml"
DEPTH_RESULT_PATH = ROOT / "results" / "te-noise-depth.json"
OUTPUT_PATH = ROOT / "results" / "te-pixel-covariance.json"


def spin_maps(e_alm: np.ndarray, b_alm: np.ndarray, nside: int, lmax: int) -> np.ndarray:
    return np.asarray(hp.alm2map_spin([e_alm, b_alm], nside=nside, spin=2, lmax=lmax))


def flatten_observed(qu: np.ndarray, observed: np.ndarray) -> np.ndarray:
    return np.concatenate((qu[0, observed], qu[1, observed]))


def expand_observed(vector: np.ndarray, observed: np.ndarray, npix: int) -> np.ndarray:
    size = observed.size
    qu = np.zeros((2, npix), dtype=float)
    qu[0, observed] = vector[:size]
    qu[1, observed] = vector[size:]
    return qu


def noise_sigma(nside: int, base_rms_uk: float) -> np.ndarray:
    theta, _ = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    depth = 1.0 + 2.0 * np.square(np.cos(theta))
    return base_rms_uk * depth / CMB_TEMPERATURE_UK


@dataclass
class PixelCovariance:
    nside: int
    lmax: int
    observed: np.ndarray
    signal_cl: np.ndarray
    noise_variance: np.ndarray

    def __post_init__(self) -> None:
        self.npix = hp.nside2npix(self.nside)
        self.pixel_area = hp.nside2pixarea(self.nside)
        dimension = 2 * self.observed.size
        self.operator = LinearOperator((dimension, dimension), matvec=self.matvec, dtype=float)
        diagonal_signal = float(
            np.sum((2 * np.arange(self.signal_cl.size) + 1) * self.signal_cl) / (4 * math.pi)
        )
        diagonal = np.concatenate(
            (
                diagonal_signal + self.noise_variance[self.observed],
                diagonal_signal + self.noise_variance[self.observed],
            )
        )
        self.preconditioner = LinearOperator(
            (dimension, dimension), matvec=lambda vector: vector / diagonal, dtype=float
        )

    def matvec(self, vector: np.ndarray) -> np.ndarray:
        qu = expand_observed(vector, self.observed, self.npix)
        e_alm, _ = hp.map2alm_spin(qu, spin=2, lmax=self.lmax)
        signal_qu = spin_maps(
            hp.almxfl(e_alm, self.signal_cl / self.pixel_area),
            np.zeros_like(e_alm),
            self.nside,
            self.lmax,
        )
        signal_qu[:, self.observed] += qu[:, self.observed] * self.noise_variance[self.observed]
        return flatten_observed(signal_qu, self.observed)

    def solve(self, vector: np.ndarray, analysis: dict[str, Any]) -> tuple[np.ndarray, dict[str, float | int]]:
        iterations = 0

        def callback(_: np.ndarray) -> None:
            nonlocal iterations
            iterations += 1

        solution, info = cg(
            self.operator,
            vector,
            rtol=float(analysis["cg_relative_tolerance"]),
            atol=float(analysis["cg_absolute_tolerance"]),
            maxiter=int(analysis["cg_maximum_iterations"]),
            M=self.preconditioner,
            callback=callback,
        )
        residual = self.operator @ solution - vector
        relative_residual = float(np.linalg.norm(residual) / np.linalg.norm(vector))
        if info != 0 or relative_residual > float(analysis["maximum_accepted_relative_residual"]):
            raise RuntimeError(
                f"Pixel inverse solve failed: info={info}, relative_residual={relative_residual}"
            )
        return solution, {
            "iterations": iterations,
            "relative_residual": relative_residual,
            "info": int(info),
        }


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    stress, base_contract, template, template_path = load_contracts()
    depth = json.loads(DEPTH_RESULT_PATH.read_text())
    inherited = contract["inherit"]
    expected = {
        "masked_contract": str(BASE_CONTRACT_PATH.relative_to(ROOT)),
        "systematics_contract": str(STRESS_CONTRACT_PATH.relative_to(ROOT)),
        "depth_contract": str(DEPTH_CONTRACT_PATH.relative_to(ROOT)),
        "depth_result": str(DEPTH_RESULT_PATH.relative_to(ROOT)),
    }
    if inherited != expected:
        raise RuntimeError("Pixel covariance gate does not match frozen inherited artifacts")
    specified_depth = float(contract["analysis"]["base_noise_rms_uK_per_pixel"])
    result_depth = float(depth["calibrated_depth"]["base_rms_uK_per_pixel"])
    if specified_depth != result_depth:
        raise RuntimeError("Pixel covariance gate must use the previously frozen noise depth exactly")
    return contract, stress, base_contract, template, template_path


def nuisance_projected_inverse_template(
    covariance: PixelCovariance,
    template: np.ndarray,
    nuisances: np.ndarray,
    analysis: dict[str, Any],
) -> tuple[np.ndarray, float, list[dict[str, float | int]]]:
    inverse_template, template_diagnostic = covariance.solve(template, analysis)
    inverse_nuisances: list[np.ndarray] = []
    diagnostics: list[dict[str, float | int]] = [template_diagnostic]
    for nuisance in nuisances:
        inverse_nuisance, diagnostic = covariance.solve(nuisance, analysis)
        inverse_nuisances.append(inverse_nuisance)
        diagnostics.append(diagnostic)
    inverse_nuisance_matrix = np.column_stack(inverse_nuisances)
    gram = nuisances @ inverse_nuisance_matrix
    coefficients = np.linalg.solve(gram, nuisances @ inverse_template)
    projected = inverse_template - inverse_nuisance_matrix @ coefficients
    information = float(template @ projected)
    if information <= 0:
        raise RuntimeError("Nuisance-projected pixel information must be positive")
    return projected, information, diagnostics


def generate() -> dict[str, Any]:
    contract, stress, base_contract, template, template_path = load_inputs()
    analysis = contract["analysis"]
    validation_config = contract["validation"]
    base = stress["base"]
    truth = stress["sky_truth"]
    assumptions = stress["analysis_assumptions"]
    nside = int(base["nside"])
    lmax = int(base["lmax"])
    npix = hp.nside2npix(nside)

    _, _, regression, conditional_cl = cmb_covariance(lmax)
    _, _, conditional_signal = physical_alms(template, base_contract, regression)
    injection_amplitude = float(base["injection_sigma"]) / math.sqrt(
        harmonic_dot(conditional_signal, conditional_signal, conditional_cl, lmax)
    )
    true_beam = beam_window(float(truth["beam_fwhm_arcmin"]), lmax)
    assumed_beam = beam_window(float(assumptions["beam_fwhm_arcmin"]), lmax)
    zero_b = np.zeros_like(conditional_signal)
    true_signal_qu = spin_maps(hp.almxfl(conditional_signal, true_beam), zero_b, nside, lmax)
    assumed_template_qu = spin_maps(
        hp.almxfl(conditional_signal, assumed_beam), zero_b, nside, lmax
    )
    gain = float(truth["polarization_gain"])
    angle_deg = float(truth["polarization_angle_error_deg"])
    fixed_signal_qu = injection_amplitude * rotate_and_gain(true_signal_qu, gain, angle_deg)

    true_foregrounds, _ = generate_foregrounds(
        nside, list(truth["foreground_presets"]), float(truth["frequency_ghz"])
    )
    model_foregrounds, _ = generate_foregrounds(
        nside, list(assumptions["nuisance_presets"]), float(assumptions["frequency_ghz"])
    )
    true_foregrounds = np.asarray(
        [beam_qu_maps(component, true_beam, nside, lmax) for component in true_foregrounds]
    )
    model_foregrounds = np.asarray(
        [beam_qu_maps(component, assumed_beam, nside, lmax) for component in model_foregrounds]
    )
    fixed_foreground_qu = rotate_and_gain(np.sum(true_foregrounds, axis=0), gain, angle_deg)

    mask, binary_fsky, effective_fsky = make_mask(base_contract)
    theta, _ = hp.pix2ang(nside, np.arange(npix))
    latitude = 90.0 - np.degrees(theta)
    observed = np.flatnonzero(
        np.abs(latitude) >= float(base_contract["mask"]["rejected_latitude_band_deg"])
    )
    sigma = noise_sigma(nside, float(analysis["base_noise_rms_uK_per_pixel"]))
    covariance = PixelCovariance(
        nside=nside,
        lmax=lmax,
        observed=observed,
        signal_cl=conditional_cl * np.square(assumed_beam),
        noise_variance=np.square(sigma),
    )
    template_vector = flatten_observed(assumed_template_qu, observed)
    b_template_vector = flatten_observed(
        spin_maps(zero_b, hp.almxfl(conditional_signal, assumed_beam), nside, lmax), observed
    )
    nuisance_vectors = np.asarray(
        [flatten_observed(component, observed) for component in model_foregrounds]
    )
    inverse_e, e_information, e_solves = nuisance_projected_inverse_template(
        covariance, template_vector, nuisance_vectors, analysis
    )
    inverse_b, b_information, b_solves = nuisance_projected_inverse_template(
        covariance, b_template_vector, nuisance_vectors, analysis
    )

    fixed_vector = flatten_observed(fixed_signal_qu + fixed_foreground_qu, observed)
    records: list[dict[str, float | int | bool]] = []
    start = int(validation_config["independent_seed_start"])
    count = int(validation_config["seed_count"])
    detection_threshold = float(validation_config["detection_threshold_sigma"])
    signal_cl_truth = conditional_cl * np.square(true_beam)
    rotation = math.radians(2.0 * angle_deg)
    for offset in range(count):
        seed = start + offset
        np.random.seed(seed)
        cmb_e = hp.synalm(signal_cl_truth, lmax=lmax, new=True)
        cmb_qu = spin_maps(
            gain * math.cos(rotation) * cmb_e,
            gain * math.sin(rotation) * cmb_e,
            nside,
            lmax,
        )
        generator = np.random.default_rng(seed + 1)
        noise_qu = generator.normal(size=(2, npix)) * sigma
        data_vector = fixed_vector + flatten_observed(cmb_qu + noise_qu, observed)
        e_score = float(data_vector @ inverse_e / math.sqrt(e_information))
        b_score = float(data_vector @ inverse_b / math.sqrt(b_information))
        records.append(
            {
                "seed": seed,
                "e_score_sigma": e_score,
                "b_score_sigma": b_score,
                "detected": e_score >= detection_threshold,
            }
        )

    e_scores = np.asarray([record["e_score_sigma"] for record in records], dtype=float)
    b_scores = np.asarray([record["b_score_sigma"] for record in records], dtype=float)
    successes = int(sum(bool(record["detected"]) for record in records))
    finite = bool(np.all(np.isfinite(e_scores)) and np.all(np.isfinite(b_scores)))
    maximum_b = float(np.max(np.abs(b_scores)))
    all_solves = e_solves + b_solves
    checks = {
        "inverse_solves": all(
            float(diagnostic["relative_residual"])
            <= float(analysis["maximum_accepted_relative_residual"])
            for diagnostic in all_solves
        ),
        "seed_detection_count": successes >= int(validation_config["minimum_detection_successes"]),
        "finite_scores": finite,
        "b_diagnostic": maximum_b < float(validation_config["maximum_absolute_b_diagnostic_sigma"]),
    }
    return {
        "experiment_id": contract["experiment_id"],
        "status": "PASS" if all(checks.values()) else "FAIL",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "depth_result_sha256": sha256(DEPTH_RESULT_PATH),
            "systematics_contract_sha256": sha256(STRESS_CONTRACT_PATH),
        },
        "provenance": {
            "physical_template_path": str(template_path.relative_to(ROOT)),
            "physical_template_sha256": sha256(template_path),
            "healpy_version": hp.__version__,
            "namaster_version": nmt.__version__,
            "pysm3_version": pysm3.__version__,
            "observational_cmb_maps_opened": False,
            "planck_accessed": False,
        },
        "geometry": {
            "nside": nside,
            "lmax": lmax,
            "observed_pixel_count": int(observed.size),
            "binary_sky_fraction": binary_fsky,
            "effective_apodized_sky_fraction": effective_fsky,
        },
        "inverse_filter": {
            "matrix_dimension": int(2 * observed.size),
            "explicit_dense_matrix_allocated": False,
            "signal_operator": "spin-2 harmonic CAMB conditional E covariance",
            "noise_operator": "exact diagonal anisotropic Q/U pixel variance",
            "nuisance_modes": list(assumptions["nuisance_presets"]),
            "e_information": e_information,
            "b_information": b_information,
            "solve_diagnostics": all_solves,
        },
        "validation": {
            "successes": successes,
            "trials": count,
            "success_fraction": successes / count,
            "e_score_mean": float(np.mean(e_scores)),
            "e_score_sample_std": float(np.std(e_scores, ddof=1)),
            "e_score_minimum": float(np.min(e_scores)),
            "e_score_maximum": float(np.max(e_scores)),
            "b_score_mean": float(np.mean(b_scores)),
            "b_score_sample_std": float(np.std(b_scores, ddof=1)),
            "maximum_absolute_b_score": maximum_b,
        },
        "seed_records": records,
        "checks": checks,
        "limitations": [
            "Synthetic cut-sky CMB-plus-noise maps only; no observational polarization or Planck product was opened.",
            "Pixel covariance includes exact inherited anisotropic white-noise variance but not correlated 1/f or bandpass-map covariance.",
            "Binary accepted sky is inverse-filtered; apodized NaMaster purification remains validated in the separate masked operator gate.",
            "The 58-of-64 rule is finite calibration, not a lower confidence bound proving 90 percent population power.",
            "Passing or failing is method evidence, not observational evidence for a bubble collision or multiverse.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "geometry", "inverse_filter", "validation", "checks")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
