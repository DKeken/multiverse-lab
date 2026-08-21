#!/usr/bin/env python3
"""Run the frozen synthetic conditional-E systematic-mismatch stress test.

GPL-3.0-or-later. This module never opens observational CMB maps.
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

from masked_te_injection import (
    CMB_TEMPERATURE_UK,
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

CONTRACT_PATH = ROOT / "research" / "te-systematics-stress.yml"
OUTPUT_PATH = ROOT / "results" / "te-systematics-stress.json"
BASE_CONTRACT_PATH = ROOT / "research" / "masked-te-injection.yml"


def beam_window(fwhm_arcmin: float, lmax: int) -> np.ndarray:
    return hp.gauss_beam(math.radians(fwhm_arcmin / 60.0), lmax=lmax, pol=False)


def beam_qu_maps(qu: np.ndarray, beam: np.ndarray, nside: int, lmax: int) -> np.ndarray:
    e_alm, b_alm = hp.map2alm_spin(qu, spin=2, lmax=lmax)
    return np.asarray(
        hp.alm2map_spin(
            [hp.almxfl(e_alm, beam), hp.almxfl(b_alm, beam)],
            nside=nside,
            spin=2,
            lmax=lmax,
        )
    )


def rotate_and_gain(qu: np.ndarray, gain: float, angle_deg: float) -> np.ndarray:
    angle = math.radians(2.0 * angle_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    q_map, u_map = qu
    return gain * np.asarray([q_map * cosine - u_map * sine, q_map * sine + u_map * cosine])


def anisotropic_noise(
    nside: int,
    base_rms_uk: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    theta, _ = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    depth = 1.0 + 2.0 * np.square(np.cos(theta))
    sigma = base_rms_uk * depth / CMB_TEMPERATURE_UK
    generator = np.random.default_rng(seed)
    noise = generator.normal(size=(2, sigma.size)) * sigma
    return noise, sigma, float(np.mean(np.square(sigma)) * hp.nside2pixarea(nside))


def load_contracts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    base_contract = yaml.safe_load(BASE_CONTRACT_PATH.read_text())
    base = contract["base"]
    base_inputs = base_contract["inputs"]
    inherited = {
        "basis": base_inputs["basis"],
        "nside": base_inputs["nside"],
        "lmax": base_inputs["template_lmax"],
        "injection_center_galactic_deg": base_inputs["injection_center_galactic_deg"],
    }
    requested = {
        "basis": base["basis"],
        "nside": base["nside"],
        "lmax": base["lmax"],
        "injection_center_galactic_deg": base["injection_center_galactic_deg"],
    }
    if requested != inherited:
        raise RuntimeError("Systematics stress geometry must match the frozen masked-injection gate")
    template_path = ROOT / base["physical_template"]
    template = json.loads(template_path.read_text())
    return contract, base_contract, template, template_path


def generate() -> dict[str, Any]:
    contract, base_contract, template, template_path = load_contracts()
    base = contract["base"]
    truth = contract["sky_truth"]
    assumptions = contract["analysis_assumptions"]
    nside = int(base["nside"])
    lmax = int(base["lmax"])

    _, _, regression, conditional_covariance = cmb_covariance(lmax)
    _, _, conditional_signal = physical_alms(template, base_contract, regression)
    full_information = harmonic_dot(conditional_signal, conditional_signal, conditional_covariance, lmax)
    injection_amplitude = float(base["injection_sigma"]) / math.sqrt(full_information)

    true_beam = beam_window(float(truth["beam_fwhm_arcmin"]), lmax)
    assumed_beam = beam_window(float(assumptions["beam_fwhm_arcmin"]), lmax)
    np.random.seed(int(base["seed"]))
    random_conditional_e = hp.synalm(conditional_covariance, lmax=lmax, new=True)
    zero_b = np.zeros_like(random_conditional_e)

    conditional_null_alm = hp.almxfl(random_conditional_e, true_beam)
    conditional_signal_alm = conditional_null_alm + injection_amplitude * hp.almxfl(conditional_signal, true_beam)
    qu_null = np.asarray(
        hp.alm2map_spin([conditional_null_alm, zero_b], nside=nside, spin=2, lmax=lmax)
    )
    qu_signal = np.asarray(
        hp.alm2map_spin([conditional_signal_alm, zero_b], nside=nside, spin=2, lmax=lmax)
    )
    assumed_template_alm = hp.almxfl(conditional_signal, assumed_beam)
    qu_template = np.asarray(
        hp.alm2map_spin([assumed_template_alm, zero_b], nside=nside, spin=2, lmax=lmax)
    )

    true_foregrounds, true_foreground_rms = generate_foregrounds(
        nside,
        list(truth["foreground_presets"]),
        float(truth["frequency_ghz"]),
    )
    model_foregrounds, model_foreground_rms = generate_foregrounds(
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
    true_foreground_sum = np.sum(true_foregrounds, axis=0)

    gain = float(truth["polarization_gain"])
    angle_error = float(truth["polarization_angle_error_deg"])
    calibrated_null = rotate_and_gain(qu_null, gain, angle_error)
    calibrated_signal = rotate_and_gain(qu_signal, gain, angle_error)
    calibrated_foreground = rotate_and_gain(true_foreground_sum, gain, angle_error)
    noise, sigma_pixel, white_noise_cl = anisotropic_noise(
        nside,
        float(truth["noise_rms_uK_per_pixel"]),
        int(base["seed"]) + 1,
    )
    null_only_maps = calibrated_null + noise
    foreground_null_maps = calibrated_null + calibrated_foreground + noise
    foreground_signal_maps = calibrated_signal + calibrated_foreground + noise

    mask, binary_fsky, effective_fsky = make_mask(base_contract)
    analysis_covariance = conditional_covariance * np.square(assumed_beam) + white_noise_cl
    template_alms = field_alms(mask, qu_template, model_foregrounds, lmax)
    null_only_alms = field_alms(mask, null_only_maps, model_foregrounds, lmax)
    foreground_null_alms = field_alms(mask, foreground_null_maps, model_foregrounds, lmax)
    foreground_signal_alms = field_alms(mask, foreground_signal_maps, model_foregrounds, lmax)

    processed_information = harmonic_dot(
        template_alms[0], template_alms[0], analysis_covariance, lmax
    )
    expected_response_score = injection_amplitude * math.sqrt(processed_information)
    injection_response = foreground_signal_alms - foreground_null_alms
    injection_response_score = filtered_score(
        injection_response[0], template_alms[0], analysis_covariance, lmax
    )
    fractional_response_bias = injection_response_score / expected_response_score - 1.0
    foreground_residual_score = filtered_score(
        foreground_null_alms[0] - null_only_alms[0],
        template_alms[0],
        analysis_covariance,
        lmax,
    )
    total_recovery_score = filtered_score(
        foreground_signal_alms[0], template_alms[0], analysis_covariance, lmax
    )
    total_b_score = filtered_score(
        foreground_signal_alms[1], template_alms[0], analysis_covariance, lmax
    )

    thresholds = {
        "maximum_absolute_fractional_injection_response_bias": 0.20,
        "maximum_absolute_foreground_residual_sigma": 1.0,
        "maximum_absolute_b_score_sigma": 1.0,
        "minimum_total_recovery_score_sigma": 3.0,
    }
    checks = {
        "injection_response_bias": abs(fractional_response_bias)
        <= thresholds["maximum_absolute_fractional_injection_response_bias"],
        "foreground_residual": abs(foreground_residual_score)
        <= thresholds["maximum_absolute_foreground_residual_sigma"],
        "b_veto": abs(total_b_score) < thresholds["maximum_absolute_b_score_sigma"],
        "total_recovery": total_recovery_score >= thresholds["minimum_total_recovery_score_sigma"],
    }
    return {
        "experiment_id": contract["experiment_id"],
        "status": "PASS" if all(checks.values()) else "FAIL",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "thresholds": thresholds,
            "frozen_truth": truth,
            "frozen_analysis_assumptions": assumptions,
        },
        "provenance": {
            "physical_template_path": str(template_path.relative_to(ROOT)),
            "physical_template_sha256": sha256(template_path),
            "base_contract_path": str(BASE_CONTRACT_PATH.relative_to(ROOT)),
            "base_contract_sha256": sha256(BASE_CONTRACT_PATH),
            "healpy_version": hp.__version__,
            "namaster_version": nmt.__version__,
            "pysm3_version": pysm3.__version__,
            "observational_cmb_maps_opened": False,
            "planck_accessed": False,
        },
        "mask": {
            "binary_sky_fraction": binary_fsky,
            "effective_apodized_sky_fraction": effective_fsky,
        },
        "noise": {
            "minimum_rms_uK_per_pixel": float(np.min(sigma_pixel) * CMB_TEMPERATURE_UK),
            "maximum_rms_uK_per_pixel": float(np.max(sigma_pixel) * CMB_TEMPERATURE_UK),
            "mean_square_white_noise_cl": white_noise_cl,
        },
        "foregrounds": {
            "truth_component_rms": true_foreground_rms,
            "analysis_component_rms": model_foreground_rms,
            "truth_and_analysis_models_match": False,
        },
        "recovery": {
            "full_sky_conditional_information": full_information,
            "processed_analysis_information": processed_information,
            "injected_unit_basis_amplitude": injection_amplitude,
            "expected_injection_response_score_sigma": expected_response_score,
            "measured_injection_response_score_sigma": injection_response_score,
            "fractional_injection_response_bias": fractional_response_bias,
            "foreground_residual_score_sigma": foreground_residual_score,
            "total_recovery_score_sigma": total_recovery_score,
            "total_purified_b_score_sigma": total_b_score,
        },
        "checks": checks,
        "limitations": [
            "Synthetic CMB and PySM foregrounds only; no observational polarization or Planck product was opened.",
            "This is one fixed adversarial scenario, not a calibrated distribution of systematic uncertainty.",
            "Temperature-systematic and T-to-E regression errors are not varied in this polarization-focused stress test.",
            "Noise covariance uses the mean frozen pixel variance rather than the full anisotropic pixel covariance.",
            "Passing or failing this gate is method evidence, not observational evidence for a bubble collision or multiverse.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
