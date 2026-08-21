from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import camb
import healpy as hp
import numpy as np

from cmb_fixture_repro import LMAX, bubble_template, matched_filter_transfer, theory_background_cl
from joint_te_gate import calibrate

SCALE_DEG = 5.0
BEAM_FWHM_ARCMIN = 60.0


def camb_cls() -> tuple[np.ndarray, dict[str, float]]:
    parameters = camb.CAMBparams()
    cosmology = {
        "H0": 67.5,
        "ombh2": 0.022,
        "omch2": 0.122,
        "tau": 0.06,
        "As": 2.0e-9,
        "ns": 0.965,
    }
    parameters.set_cosmology(
        H0=cosmology["H0"],
        ombh2=cosmology["ombh2"],
        omch2=cosmology["omch2"],
        tau=cosmology["tau"],
    )
    parameters.InitPower.set_params(As=cosmology["As"], ns=cosmology["ns"])
    parameters.set_for_lmax(LMAX, lens_potential_accuracy=0)
    result = camb.get_results(parameters)
    spectra = result.get_lensed_scalar_cls(lmax=LMAX, CMB_unit="muK", raw_cl=True)
    return spectra, cosmology


def filtered_covariance(root: Path, spectra: np.ndarray) -> dict[str, Any]:
    background = theory_background_cl(
        root / "vendor" / "s2fil" / "data_in" / "wmap_lcdm_pl_model_wmap7baoh0_CAMB.dat",
        noise_std=0.0,
        beam_fwhm_arcmin=BEAM_FWHM_ARCMIN,
        output_unit="K",
    )
    transfer = matched_filter_transfer(
        bubble_template(SCALE_DEG),
        background,
        beam_fwhm_arcmin=BEAM_FWHM_ARCMIN,
    )
    ell = np.arange(LMAX + 1)
    multiplicity = (2.0 * ell + 1.0) / (4.0 * np.pi)
    weights = multiplicity * np.square(transfer)
    tt = spectra[:, 0]
    ee = spectra[:, 1]
    te = spectra[:, 3]
    variance_t = float(np.sum(weights[2:] * tt[2:]))
    variance_e = float(np.sum(weights[2:] * ee[2:]))
    covariance_te = float(np.sum(weights[2:] * te[2:]))
    rho = covariance_te / math.sqrt(variance_t * variance_e)
    if not -1.0 < rho < 1.0 or rho == 0.0:
        raise ValueError("filtered CAMB covariance is singular or uncorrelated")

    absolute_information = weights[2:] * np.sqrt(tt[2:] * ee[2:])
    cumulative = np.cumsum(absolute_information) / np.sum(absolute_information)
    ell_50 = int(np.searchsorted(cumulative, 0.5)) + 2
    ell_90 = int(np.searchsorted(cumulative, 0.9)) + 2
    return {
        "scale_deg": SCALE_DEG,
        "beam_fwhm_arcmin": BEAM_FWHM_ARCMIN,
        "effective_rho": rho,
        "filtered_tt_variance_microkelvin2": variance_t,
        "filtered_ee_variance_microkelvin2": variance_e,
        "filtered_te_covariance_microkelvin2": covariance_te,
        "absolute_information_ell_50": ell_50,
        "absolute_information_ell_90": ell_90,
        "te_sign_changes": int(np.count_nonzero(np.diff(np.signbit(te[2:])))),
    }


def run(root: Path) -> dict[str, Any]:
    spectra, cosmology = camb_cls()
    covariance = filtered_covariance(root, spectra)
    rho = float(covariance["effective_rho"])
    orientations = {
        "aligned": calibrate(rho=rho),
        "anti_aligned": calibrate(rho=-rho),
    }
    conditional_rates = [
        result["null_calibration"]["conditional_rate"] for result in orientations.values()
    ]
    naive_rates = [result["null_calibration"]["naive_selected_e_rate"] for result in orientations.values()]
    return {
        "experiment_id": "camb-te-selection-calibration-v1",
        "epistemic_class": "ADAPTED",
        "status": "PASS" if all(item["status"] == "PASS" for item in orientations.values()) else "FAIL",
        "interpretation": "CAMB Lambda-CDM covariance calibration only; no observational polarization map or bubble E template was accessed.",
        "engine": {"name": "CAMB", "version": camb.__version__, "cosmology": cosmology},
        "filter": covariance,
        "orientations": orientations,
        "summary": {
            "naive_false_positive_rate_min": min(naive_rates),
            "naive_false_positive_rate_max": max(naive_rates),
            "conditional_false_positive_rate_min": min(conditional_rates),
            "conditional_false_positive_rate_max": max(conditional_rates),
        },
        "next_gate": "Generate physical bubble T/E templates from Feeney et al. Eq. 2-4, then freeze orientation before observational access.",
        "forbidden_claim": "This covariance calculation is not a bubble template, observation, detection, or holdout result.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("results/camb-te-selection.json"))
    args = parser.parse_args()
    result = run(args.root)
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
