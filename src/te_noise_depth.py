#!/usr/bin/env python3
"""Forecast and calibrate the frozen conditional-E pixel-noise requirement.

GPL-3.0-or-later. Synthetic harmonic realizations only; no observational maps.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import healpy as hp
import numpy as np
import pymaster as nmt
import pysm3
import yaml
from scipy.optimize import brentq

from masked_te_injection import (
    ROOT,
    cmb_covariance,
    field_alms,
    filtered_score,
    generate_foregrounds,
    harmonic_dot,
    make_mask,
    physical_alms,
    sha256,
)
from te_systematics_stress import (
    BASE_CONTRACT_PATH,
    CONTRACT_PATH as STRESS_CONTRACT_PATH,
    anisotropic_noise,
    beam_qu_maps,
    beam_window,
    load_contracts,
    rotate_and_gain,
)

CONTRACT_PATH = ROOT / "research" / "te-noise-depth.yml"
OUTPUT_PATH = ROOT / "results" / "te-noise-depth.json"


def load_depth_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def validate_inheritance(depth: dict[str, Any]) -> None:
    inherited = depth["inherit"]
    expected = {
        "masked_contract": str(BASE_CONTRACT_PATH.relative_to(ROOT)),
        "systematics_contract": str(STRESS_CONTRACT_PATH.relative_to(ROOT)),
        "physical_template": "results/bubble-te-template.json",
    }
    if inherited != expected:
        raise RuntimeError("Noise-depth gate must inherit the frozen masked and mismatch contracts exactly")


def prepare_context() -> dict[str, Any]:
    stress, base_contract, template, template_path = load_contracts()
    base = stress["base"]
    truth = stress["sky_truth"]
    assumptions = stress["analysis_assumptions"]
    nside = int(base["nside"])
    lmax = int(base["lmax"])
    _, _, regression, conditional_covariance = cmb_covariance(lmax)
    _, _, conditional_signal = physical_alms(template, base_contract, regression)
    full_information = harmonic_dot(conditional_signal, conditional_signal, conditional_covariance, lmax)
    injection_amplitude = float(base["injection_sigma"]) / math.sqrt(full_information)
    zero_b = np.zeros_like(conditional_signal)

    true_beam = beam_window(float(truth["beam_fwhm_arcmin"]), lmax)
    assumed_beam = beam_window(float(assumptions["beam_fwhm_arcmin"]), lmax)
    true_signal_qu = np.asarray(
        hp.alm2map_spin(
            [hp.almxfl(conditional_signal, true_beam), zero_b],
            nside=nside,
            spin=2,
            lmax=lmax,
        )
    )
    assumed_template_qu = np.asarray(
        hp.alm2map_spin(
            [hp.almxfl(conditional_signal, assumed_beam), zero_b],
            nside=nside,
            spin=2,
            lmax=lmax,
        )
    )
    true_foregrounds, _ = generate_foregrounds(
        nside,
        list(truth["foreground_presets"]),
        float(truth["frequency_ghz"]),
    )
    model_foregrounds, _ = generate_foregrounds(
        nside,
        list(assumptions["nuisance_presets"]),
        float(assumptions["frequency_ghz"]),
    )
    true_foregrounds = np.asarray(
        [beam_qu_maps(component, true_beam, nside, lmax) for component in true_foregrounds]
    )
    model_foregrounds = np.asarray(
        [beam_qu_maps(component, assumed_beam, nside, lmax) for component in model_foregrounds]
    )
    gain = float(truth["polarization_gain"])
    angle = float(truth["polarization_angle_error_deg"])
    fixed_signal_qu = injection_amplitude * rotate_and_gain(true_signal_qu, gain, angle)
    fixed_foreground_qu = rotate_and_gain(np.sum(true_foregrounds, axis=0), gain, angle)
    mask, binary_fsky, effective_fsky = make_mask(base_contract)
    template_alms = field_alms(mask, assumed_template_qu, model_foregrounds, lmax)
    signal_alms = field_alms(mask, fixed_signal_qu, model_foregrounds, lmax)
    foreground_alms = field_alms(mask, fixed_foreground_qu, model_foregrounds, lmax)
    fixed_alms = signal_alms + foreground_alms
    return {
        "base": base,
        "truth": truth,
        "assumptions": assumptions,
        "template_path": template_path,
        "nside": nside,
        "lmax": lmax,
        "conditional_covariance": conditional_covariance,
        "true_beam": true_beam,
        "assumed_beam": assumed_beam,
        "template_alms": template_alms,
        "fixed_alms": fixed_alms,
        "binary_fsky": binary_fsky,
        "effective_fsky": effective_fsky,
        "injection_amplitude": injection_amplitude,
    }


def white_noise_cl(nside: int, base_rms_uk: float) -> float:
    _, _, level = anisotropic_noise(nside, base_rms_uk, seed=0)
    return level


def analysis_covariance(context: dict[str, Any], base_rms_uk: float) -> np.ndarray:
    return (
        context["conditional_covariance"] * np.square(context["assumed_beam"])
        + white_noise_cl(context["nside"], base_rms_uk)
    )


def mean_score(context: dict[str, Any], base_rms_uk: float) -> float:
    covariance = analysis_covariance(context, base_rms_uk)
    return filtered_score(
        context["fixed_alms"][0],
        context["template_alms"][0],
        covariance,
        context["lmax"],
    )


def solve_depth(context: dict[str, Any], contract: dict[str, Any]) -> tuple[float, dict[str, float]]:
    forecast = contract["forecast"]
    search = forecast["base_noise_search_uK_per_pixel"]
    minimum = float(search["minimum"])
    maximum = float(search["maximum"])
    required = float(forecast["gaussian_required_mean_sigma"])
    minimum_score = mean_score(context, minimum)
    maximum_score = mean_score(context, maximum)
    if not (minimum_score > required > maximum_score):
        raise RuntimeError("Frozen search interval does not bracket a unique noise-depth root")
    root = float(
        brentq(
            lambda depth: mean_score(context, depth) - required,
            minimum,
            maximum,
            xtol=float(forecast["solver_absolute_tolerance_uK_per_pixel"]),
        )
    )
    return root, {
        "zero_noise_mean_score_sigma": minimum_score,
        "maximum_search_noise_mean_score_sigma": maximum_score,
        "required_mean_score_sigma": required,
        "root_mean_score_sigma": mean_score(context, root),
    }


def seeded_scores(
    context: dict[str, Any],
    contract: dict[str, Any],
    depth: float,
) -> tuple[list[dict[str, float | int | bool]], dict[str, float | int]]:
    validation = contract["validation"]
    lmax = context["lmax"]
    covariance = analysis_covariance(context, depth)
    noise_level = white_noise_cl(context["nside"], depth)
    truth = context["truth"]
    gain = float(truth["polarization_gain"])
    angle = math.radians(2.0 * float(truth["polarization_angle_error_deg"]))
    cmb_covariance = context["conditional_covariance"] * np.square(context["true_beam"])
    records: list[dict[str, float | int | bool]] = []
    start = int(validation["independent_seed_start"])
    count = int(validation["seed_count"])
    threshold = float(contract["forecast"]["detection_threshold_sigma"])
    for offset in range(count):
        seed = start + offset
        np.random.seed(seed)
        cmb_e = hp.synalm(cmb_covariance, lmax=lmax, new=True)
        noise_e = hp.synalm(np.full(lmax + 1, noise_level), lmax=lmax, new=True)
        noise_b = hp.synalm(np.full(lmax + 1, noise_level), lmax=lmax, new=True)
        stochastic_e = gain * math.cos(angle) * cmb_e + noise_e
        stochastic_b = gain * math.sin(angle) * cmb_e + noise_b
        e_score = filtered_score(
            context["fixed_alms"][0] + stochastic_e,
            context["template_alms"][0],
            covariance,
            lmax,
        )
        b_score = filtered_score(
            context["fixed_alms"][1] + stochastic_b,
            context["template_alms"][0],
            covariance,
            lmax,
        )
        records.append(
            {
                "seed": seed,
                "e_score_sigma": e_score,
                "b_score_sigma": b_score,
                "detected": e_score >= threshold,
            }
        )
    e_scores = np.asarray([record["e_score_sigma"] for record in records], dtype=float)
    b_scores = np.asarray([record["b_score_sigma"] for record in records], dtype=float)
    successes = int(sum(bool(record["detected"]) for record in records))
    summary: dict[str, float | int] = {
        "successes": successes,
        "trials": count,
        "success_fraction": successes / count,
        "e_score_mean": float(np.mean(e_scores)),
        "e_score_sample_std": float(np.std(e_scores, ddof=1)),
        "e_score_minimum": float(np.min(e_scores)),
        "e_score_maximum": float(np.max(e_scores)),
        "b_score_mean": float(np.mean(b_scores)),
        "b_score_sample_std": float(np.std(b_scores, ddof=1)),
        "maximum_absolute_b_score": float(np.max(np.abs(b_scores))),
    }
    return records, summary


def generate() -> dict[str, Any]:
    contract = load_depth_contract()
    validate_inheritance(contract)
    context = prepare_context()
    depth, forecast = solve_depth(context, contract)
    records, validation = seeded_scores(context, contract, depth)
    requirements = contract["validation"]
    finite = all(
        math.isfinite(float(record[metric]))
        for record in records
        for metric in ("e_score_sigma", "b_score_sigma")
    )
    checks = {
        "analytic_root": True,
        "seed_detection_count": int(validation["successes"])
        >= int(requirements["minimum_detection_successes"]),
        "finite_scores": finite,
    }
    return {
        "experiment_id": contract["experiment_id"],
        "status": "PASS" if all(checks.values()) else "FAIL",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "masked_contract_sha256": sha256(BASE_CONTRACT_PATH),
            "systematics_contract_sha256": sha256(STRESS_CONTRACT_PATH),
        },
        "provenance": {
            "physical_template_path": str(context["template_path"].relative_to(ROOT)),
            "physical_template_sha256": sha256(context["template_path"]),
            "healpy_version": hp.__version__,
            "namaster_version": nmt.__version__,
            "pysm3_version": pysm3.__version__,
            "observational_cmb_maps_opened": False,
            "planck_accessed": False,
        },
        "calibrated_depth": {
            "base_rms_uK_per_pixel": depth,
            "maximum_rms_uK_per_pixel": 3.0 * depth,
            "white_noise_cl": white_noise_cl(context["nside"], depth),
            **forecast,
        },
        "validation": validation,
        "seed_records": records,
        "checks": checks,
        "limitations": [
            "Synthetic harmonic CMB-plus-noise seeds only; no observational polarization or Planck product was opened.",
            "NaMaster mask/deprojection/purification morphology is fixed once; seed variation is performed in the same approximate harmonic covariance used by the statistic.",
            "The 58-of-64 rule is a preregistered finite calibration criterion, not a lower confidence bound proving 90 percent population power.",
            "One fixed foreground, beam, gain, angle, and anisotropic-depth pattern is inherited from the mismatch stress.",
            "Noise covariance uses mean pixel variance rather than the full anisotropic pixel covariance.",
            "A passing depth is a synthetic design requirement, not Planck sensitivity or observational evidence.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "calibrated_depth", "validation", "checks")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
