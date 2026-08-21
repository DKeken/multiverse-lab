#!/usr/bin/env python3
"""Run the frozen synthetic cut-sky T/E bubble injection gate.

GPL-3.0-or-later. Synthetic only: this module never opens observational CMB maps.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import camb
import healpy as hp
import numpy as np
import pymaster as nmt
import pysm3
import pysm3.units as u
import yaml
from scipy.special import sph_harm_y

from bubble_te_template import COSMOLOGY, LMIN

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "research" / "masked-te-injection.yml"
OUTPUT_PATH = ROOT / "results" / "masked-te-injection.json"
CMB_TEMPERATURE_UK = 2.7255e6


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], Path]:
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    template_path = ROOT / contract["inputs"]["physical_template"]
    template = json.loads(template_path.read_text())
    return contract, template, template_path


def axisymmetric_alm(bl0: np.ndarray, longitude_deg: float, latitude_deg: float, lmax: int) -> np.ndarray:
    theta = math.radians(90.0 - latitude_deg)
    phi = math.radians(longitude_deg)
    alm = np.zeros(hp.Alm.getsize(lmax), dtype=np.complex128)
    for ell in range(LMIN, lmax + 1):
        factor = bl0[ell] * math.sqrt(4.0 * math.pi / (2 * ell + 1))
        for order in range(ell + 1):
            index = hp.Alm.getidx(lmax, ell, order)
            alm[index] = factor * np.conjugate(sph_harm_y(ell, order, theta, phi))
    return alm


def cmb_covariance(lmax: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    parameters = camb.CAMBparams()
    parameters.set_cosmology(
        H0=COSMOLOGY["H0"],
        ombh2=COSMOLOGY["ombh2"],
        omch2=COSMOLOGY["omch2"],
        tau=COSMOLOGY["tau"],
    )
    parameters.InitPower.set_params(As=COSMOLOGY["As"], ns=COSMOLOGY["ns"])
    parameters.set_for_lmax(lmax, lens_potential_accuracy=0)
    data = camb.get_results(parameters)
    scalar = data.get_unlensed_scalar_cls(lmax=lmax, raw_cl=True)
    c_tt = scalar[:, 0]
    c_ee = scalar[:, 1]
    c_te = scalar[:, 3]
    conditional = np.zeros_like(c_tt)
    regression = np.zeros_like(c_tt)
    valid = c_tt > 0
    regression[valid] = c_te[valid] / c_tt[valid]
    conditional[valid] = c_ee[valid] - np.square(c_te[valid]) / c_tt[valid]
    if np.any(conditional[LMIN:] <= 0):
        raise RuntimeError("CAMB conditional E covariance is not positive")
    return c_tt, c_ee, regression, conditional


def physical_alms(template: dict[str, Any], contract: dict[str, Any], regression: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    inputs = contract["inputs"]
    basis = template["basis_templates"][inputs["basis"]]
    lmax = int(inputs["template_lmax"])
    ell = np.asarray(basis["ell"], dtype=int)
    if ell[0] != LMIN or ell[-1] < lmax:
        raise RuntimeError("Physical template does not cover frozen multipoles")
    temperature_bl0 = np.zeros(lmax + 1)
    e_mode_bl0 = np.zeros(lmax + 1)
    keep = ell <= lmax
    temperature_bl0[ell[keep]] = np.asarray(basis["temperature_bl0"])[keep]
    e_mode_bl0[ell[keep]] = np.asarray(basis["e_mode_bl0"])[keep]
    conditional_bl0 = e_mode_bl0 - regression * temperature_bl0
    center = inputs["injection_center_galactic_deg"]
    longitude = float(center["longitude"])
    latitude = float(center["latitude"])
    return (
        axisymmetric_alm(temperature_bl0, longitude, latitude, lmax),
        axisymmetric_alm(e_mode_bl0, longitude, latitude, lmax),
        axisymmetric_alm(conditional_bl0, longitude, latitude, lmax),
    )


def make_mask(contract: dict[str, Any]) -> tuple[np.ndarray, float, float]:
    inputs = contract["inputs"]
    mask_config = contract["mask"]
    nside = int(inputs["nside"])
    theta, _ = hp.pix2ang(nside, np.arange(hp.nside2npix(nside)))
    latitude = 90.0 - np.degrees(theta)
    binary = (np.abs(latitude) >= float(mask_config["rejected_latitude_band_deg"])).astype(float)
    mask = nmt.mask_apodization(
        binary,
        float(mask_config["apodization_deg"]),
        apotype=str(mask_config["apodization_type"]),
    )
    return mask, float(np.mean(binary)), float(np.mean(mask))


def foreground_templates(contract: dict[str, Any]) -> tuple[np.ndarray, dict[str, float]]:
    inputs = contract["inputs"]
    engines = contract["engines"]["foreground_generator"]
    nside = int(inputs["nside"])
    frequency = float(engines["frequency_ghz"]) * u.GHz
    polarized: list[np.ndarray] = []
    rms: dict[str, float] = {}
    for preset in engines["presets"]:
        sky = pysm3.Sky(nside=nside, preset_strings=[preset], output_unit=u.uK_CMB)
        emission = sky.get_emission(frequency).to_value(u.uK_CMB) / CMB_TEMPERATURE_UK
        qu = np.asarray(emission[1:3], dtype=float)
        polarized.append(qu)
        rms[preset] = float(np.sqrt(np.mean(np.square(qu))))
    return np.asarray(polarized), rms


def harmonic_dot(first: np.ndarray, second: np.ndarray, covariance: np.ndarray, lmax: int) -> float:
    ell, order = hp.Alm.getlm(lmax)
    valid = ell >= LMIN
    weight = np.zeros_like(ell, dtype=float)
    weight[valid] = np.where(order[valid] == 0, 1.0, 2.0) / covariance[ell[valid]]
    return float(np.sum(weight[valid] * np.real(first[valid] * np.conjugate(second[valid]))))


def filtered_score(data_alm: np.ndarray, template_alm: np.ndarray, covariance: np.ndarray, lmax: int) -> float:
    information = harmonic_dot(template_alm, template_alm, covariance, lmax)
    if information <= 0:
        raise RuntimeError("Processed template information must be positive")
    return harmonic_dot(data_alm, template_alm, covariance, lmax) / math.sqrt(information)


def field_alms(mask: np.ndarray, maps: np.ndarray, templates: np.ndarray, lmax: int) -> np.ndarray:
    field = nmt.NmtField(
        mask,
        maps,
        templates=templates,
        purify_e=True,
        purify_b=True,
        lmax=lmax,
        lmax_mask=lmax,
        masked_on_input=False,
        lite=True,
    )
    return np.asarray(field.get_alms())


def generate() -> dict[str, Any]:
    contract, template, template_path = load_inputs()
    inputs = contract["inputs"]
    nside = int(inputs["nside"])
    lmax = int(inputs["template_lmax"])
    c_tt, _, regression, conditional_covariance = cmb_covariance(lmax)
    signal_t, signal_e, conditional_signal = physical_alms(template, contract, regression)

    full_information = harmonic_dot(conditional_signal, conditional_signal, conditional_covariance, lmax)
    amplitude = float(inputs["injection_amplitude_sigma"]) / math.sqrt(full_information)
    np.random.seed(int(inputs["seed"]))
    random_t = hp.synalm(c_tt, lmax=lmax, new=True)
    random_conditional_e = hp.synalm(conditional_covariance, lmax=lmax, new=True)
    observed_t = random_t + amplitude * signal_t
    observed_e = hp.almxfl(random_t, regression) + random_conditional_e + amplitude * signal_e
    residual_e = observed_e - hp.almxfl(observed_t, regression)
    residual_e_null = random_conditional_e
    zero_b = np.zeros_like(residual_e)

    # Materialize all three synthetic Stokes products. Only conditional Q/U enters
    # the polarization gate; T is retained as an explicit generated-map diagnostic.
    temperature_map = hp.alm2map(observed_t, nside=nside, lmax=lmax)
    qu_null = np.asarray(hp.alm2map_spin([residual_e_null, zero_b], nside=nside, spin=2, lmax=lmax))
    qu_signal = np.asarray(hp.alm2map_spin([residual_e, zero_b], nside=nside, spin=2, lmax=lmax))
    qu_template = np.asarray(hp.alm2map_spin([conditional_signal, zero_b], nside=nside, spin=2, lmax=lmax))

    mask, binary_fsky, effective_fsky = make_mask(contract)
    foregrounds, foreground_rms = foreground_templates(contract)
    foreground_sum = np.sum(foregrounds, axis=0)

    template_alms = field_alms(mask, qu_template, foregrounds, lmax)
    null_alms = field_alms(mask, qu_null, foregrounds, lmax)
    signal_alms = field_alms(mask, qu_signal, foregrounds, lmax)
    foreground_null_alms = field_alms(mask, qu_null + foreground_sum, foregrounds, lmax)
    foreground_signal_alms = field_alms(mask, qu_signal + foreground_sum, foregrounds, lmax)

    injection_response = signal_alms - null_alms
    foreground_injection_response = foreground_signal_alms - foreground_null_alms
    processed_information = harmonic_dot(template_alms[0], template_alms[0], conditional_covariance, lmax)
    retained_snr_fraction = math.sqrt(processed_information / full_information)
    expected_processed_score = amplitude * math.sqrt(processed_information)
    recovered_response_score = filtered_score(injection_response[0], template_alms[0], conditional_covariance, lmax)
    foreground_response_score = filtered_score(
        foreground_injection_response[0], template_alms[0], conditional_covariance, lmax
    )
    foreground_total_score_delta = filtered_score(
        foreground_signal_alms[0] - signal_alms[0], template_alms[0], conditional_covariance, lmax
    )
    b_leakage_score = math.sqrt(
        harmonic_dot(injection_response[1], injection_response[1], conditional_covariance, lmax)
        / processed_information
    )

    thresholds = {
        "minimum_retained_snr_fraction": 0.8,
        "maximum_absolute_b_leakage_sigma": 1.0,
        "maximum_absolute_foreground_score_delta_sigma": 0.1,
        "minimum_binary_sky_fraction": float(contract["mask"]["accepted_sky_fraction_minimum"]),
    }
    checks = {
        "retained_snr": retained_snr_fraction >= thresholds["minimum_retained_snr_fraction"],
        "b_leakage": abs(b_leakage_score) < thresholds["maximum_absolute_b_leakage_sigma"],
        "foreground_deprojection": abs(foreground_total_score_delta)
        <= thresholds["maximum_absolute_foreground_score_delta_sigma"],
        "sky_fraction": binary_fsky >= thresholds["minimum_binary_sky_fraction"],
    }
    return {
        "experiment_id": contract["experiment_id"],
        "status": "PASS" if all(checks.values()) else "FAIL",
        "epistemic_class": contract["epistemic_class"],
        "contract": {
            "path": str(CONTRACT_PATH.relative_to(ROOT)),
            "sha256": sha256(CONTRACT_PATH),
            "frozen_inputs": inputs,
            "thresholds": thresholds,
        },
        "provenance": {
            "physical_template_path": str(template_path.relative_to(ROOT)),
            "physical_template_sha256": sha256(template_path),
            "camb_version": camb.__version__,
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
        "injection": {
            "injected_unit_basis_amplitude": amplitude,
            "full_sky_conditional_e_sigma": float(inputs["injection_amplitude_sigma"]),
            "temperature_map_rms": float(np.sqrt(np.mean(np.square(temperature_map)))),
            "conditional_q_rms": float(np.sqrt(np.mean(np.square(qu_signal[0])))),
            "conditional_u_rms": float(np.sqrt(np.mean(np.square(qu_signal[1])))),
        },
        "recovery": {
            "full_sky_conditional_information": full_information,
            "processed_cut_sky_information": processed_information,
            "retained_snr_fraction": retained_snr_fraction,
            "expected_processed_injection_score_sigma": expected_processed_score,
            "recovered_injection_response_score_sigma": recovered_response_score,
            "foreground_deprojected_injection_response_score_sigma": foreground_response_score,
            "foreground_total_score_delta_sigma": foreground_total_score_delta,
            "purified_b_leakage_score_sigma": b_leakage_score,
        },
        "foregrounds": {
            "presets": foreground_rms,
            "frequency_ghz": float(contract["engines"]["foreground_generator"]["frequency_ghz"]),
            "exact_templates_supplied_to_deprojection": True,
        },
        "checks": checks,
        "limitations": [
            "Synthetic T/Q/U only; no observational CMB polarization or Planck product was opened.",
            "Foreground deprojection receives the exact PySM templates used in the injection and does not test model mismatch.",
            "The harmonic score uses full-sky conditional covariance after NaMaster purification, not a full cut-sky pixel covariance.",
            "No beam, anisotropic instrument noise, calibration error, or frequency bandpass mismatch is included.",
            "Passing this gate is method validation, not observational evidence for a bubble collision or multiverse.",
        ],
    }


def main() -> None:
    result = generate()
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
