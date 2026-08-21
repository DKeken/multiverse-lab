from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

import healpy as hp
import numpy as np

from cmb_fixture_repro import (
    LMAX,
    NSIDE,
    SCALES_DEG,
    bubble_template,
    filter_alm,
    matched_filter_transfer,
    separated_peaks,
    theory_background_cl,
)

WMAP_BEAM_FWHM_ARCMIN = 60.0
APODIZATION_DEG = 2.0
DEFAULT_NULL_SIMULATIONS = 128
TOP_CANDIDATES_PER_SCALE = 5


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def header_dict(header: list[tuple[str, object]]) -> dict[str, object]:
    return {str(key): value for key, value, *_ in header}


def remove_masked_monopole_dipole(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    pixels = np.flatnonzero(valid)
    if len(pixels) < 4:
        raise ValueError("mask leaves too few pixels for monopole/dipole fit")
    vectors = np.asarray(hp.pix2vec(NSIDE, pixels)).T
    design = np.column_stack((np.ones(len(pixels)), vectors))
    coefficients, *_ = np.linalg.lstsq(design, values[pixels], rcond=None)
    all_vectors = np.asarray(hp.pix2vec(NSIDE, np.arange(len(values)))).T
    return values - np.column_stack((np.ones(len(values)), all_vectors)) @ coefficients


def disk_unmasked_fraction(pixel: int, scale_deg: float, core_valid: np.ndarray) -> float:
    pixels = hp.query_disc(
        NSIDE,
        hp.pix2vec(NSIDE, pixel),
        math.radians(scale_deg),
        inclusive=True,
    )
    return float(np.mean(core_valid[pixels]))


def load_wmap_and_mask(map_path: Path, mask_path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    sky_high, sky_header = hp.read_map(map_path, field=0, nest=False, h=True)
    mask_high, mask_header = hp.read_map(mask_path, field=1, nest=False, h=True)
    sky_meta = header_dict(sky_header)
    mask_meta = header_dict(mask_header)
    if hp.npix2nside(len(sky_high)) != 512 or str(sky_meta.get("ORDERING", "")).upper() != "NESTED":
        raise ValueError("WMAP ILC must declare NSIDE=512 and NESTED ordering")
    unit = str(sky_meta.get("TUNIT1", "")).lower()
    if "mk" not in unit or "thermodynamic" not in unit:
        raise ValueError(f"ambiguous WMAP temperature unit: {sky_meta.get('TUNIT1')!r}")
    if hp.npix2nside(len(mask_high)) != 512 or str(mask_meta.get("ORDERING", "")).upper() != "NESTED":
        raise ValueError("KQ75 mask must declare NSIDE=512 and NESTED ordering")
    unique_mask = np.unique(mask_high)
    if not np.array_equal(unique_mask, np.array([0.0, 1.0])):
        raise ValueError(f"KQ75 N_OBS mask must be binary, observed {unique_mask.tolist()}")

    sky_ring_kelvin = np.asarray(sky_high, dtype=np.float64) / 1000.0
    sky = hp.ud_grade(sky_ring_kelvin, NSIDE, order_in="RING", order_out="RING", power=0)
    mask_fraction = hp.ud_grade(mask_high.astype(np.float64), NSIDE, order_in="RING", order_out="RING", power=0)
    core_valid = mask_fraction >= 0.999
    sky = remove_masked_monopole_dipole(sky, core_valid)
    apodized = np.clip(
        hp.smoothing(mask_fraction, fwhm=math.radians(APODIZATION_DEG), lmax=LMAX),
        0.0,
        1.0,
    )
    return sky * apodized, core_valid, {
        "input_nside": 512,
        "analysis_nside": NSIDE,
        "input_ordering": "NESTED",
        "analysis_ordering": "RING",
        "input_unit": sky_meta.get("TUNIT1"),
        "analysis_unit": "K_CMB",
        "coordinate_system": "Galactic",
        "ilc_resolution_deg": 1.0,
        "accepted_fraction_high_resolution": float(np.mean(mask_high > 0.5)),
        "accepted_fraction_analysis_core": float(np.mean(core_valid)),
    }


def prepare_map(values: np.ndarray, core_valid: np.ndarray, apodized: np.ndarray) -> np.ndarray:
    return remove_masked_monopole_dipole(values, core_valid) * apodized


def run(root: Path, null_simulations: int, seed: int) -> dict[str, object]:
    if null_simulations < 32:
        raise ValueError("diagnostic global calibration requires at least 32 null simulations")
    map_path = root / "data" / "wmap_ilc_9yr_v5.fits"
    mask_path = root / "data" / "wmap_temperature_kq75_analysis_mask_r9_9yr_v5.fits"
    fixture = root / "vendor" / "s2fil" / "data_in"
    if not map_path.exists() or not mask_path.exists():
        raise FileNotFoundError("official WMAP ILC map and KQ75 mask are required")

    observed, core_valid, metadata = load_wmap_and_mask(map_path, mask_path)
    mask_fraction = core_valid.astype(np.float64)
    apodized = np.clip(
        hp.smoothing(mask_fraction, fwhm=math.radians(APODIZATION_DEG), lmax=LMAX),
        0.0,
        1.0,
    )
    background_cl = theory_background_cl(
        fixture / "wmap_lcdm_pl_model_wmap7baoh0_CAMB.dat",
        noise_std=0.0,
        beam_fwhm_arcmin=WMAP_BEAM_FWHM_ARCMIN,
        output_unit="K",
    )
    simulation_cl = np.where(np.isfinite(background_cl), background_cl, 0.0)
    transfers = {
        scale: matched_filter_transfer(
            bubble_template(scale),
            background_cl,
            beam_fwhm_arcmin=WMAP_BEAM_FWHM_ARCMIN,
        )
        for scale in SCALES_DEG
    }
    valid_by_scale = {scale: core_valid for scale in SCALES_DEG}

    child_seeds = np.random.SeedSequence(seed).generate_state(null_simulations)
    null_max_raw = np.zeros((null_simulations, len(SCALES_DEG)), dtype=np.float64)
    null_std_raw = np.zeros_like(null_max_raw)
    for simulation in range(null_simulations):
        np.random.seed(int(child_seeds[simulation]))
        alm = hp.synalm(simulation_cl, lmax=LMAX, new=True)
        simulated = hp.alm2map(alm, NSIDE, lmax=LMAX)
        simulated = prepare_map(simulated, core_valid, apodized)
        simulated_alm = hp.map2alm(simulated, lmax=LMAX, iter=0)
        for scale_index, scale in enumerate(SCALES_DEG):
            filtered = filter_alm(simulated_alm, transfers[scale])
            valid = valid_by_scale[scale]
            centered = filtered[valid] - np.mean(filtered[valid])
            null_std_raw[simulation, scale_index] = np.std(centered)
            null_max_raw[simulation, scale_index] = np.max(np.abs(centered))

    scale_sigma = np.median(null_std_raw, axis=0)
    if np.any(~np.isfinite(scale_sigma)) or np.any(scale_sigma <= 0):
        raise ValueError("null calibration produced invalid per-scale dispersion")
    global_null_max = np.max(null_max_raw / scale_sigma[np.newaxis, :], axis=1)
    global_threshold = float(np.quantile(global_null_max, 0.99, method="higher"))

    observed_alm = hp.map2alm(observed, lmax=LMAX, iter=3)
    scale_results: list[dict[str, object]] = []
    observed_global_max = 0.0
    for scale_index, scale in enumerate(SCALES_DEG):
        filtered = filter_alm(observed_alm, transfers[scale])
        valid = valid_by_scale[scale]
        centered = filtered - float(np.mean(filtered[valid]))
        significance = centered / scale_sigma[scale_index]
        observed_global_max = max(observed_global_max, float(np.max(np.abs(significance[valid]))))
        safe_significance = significance.copy()
        safe_significance[~valid] = 0.0
        peaks = separated_peaks(
            safe_significance,
            separation_deg=scale,
            min_significance=0.0,
            max_count=50,
        )
        candidates = []
        for peak in peaks:
            unmasked_fraction = disk_unmasked_fraction(peak.pixel, scale, core_valid)
            if unmasked_fraction < 0.8:
                continue
            longitude = math.degrees(peak.phi) % 360.0
            latitude = 90.0 - math.degrees(peak.theta)
            candidates.append({
                **asdict(peak),
                "galactic_longitude_deg": longitude,
                "galactic_latitude_deg": latitude,
                "disk_unmasked_fraction": unmasked_fraction,
                "passes_global_pilot_threshold": peak.significance >= global_threshold,
            })
            if len(candidates) >= TOP_CANDIDATES_PER_SCALE:
                break
        scale_results.append({
            "scale_deg": scale,
            "disk_unmasked_fraction_minimum": 0.8,
            "valid_sky_fraction": float(np.mean(valid)),
            "null_sigma_filtered_kelvin": float(scale_sigma[scale_index]),
            "candidates": candidates,
        })

    exceedances = int(np.count_nonzero(global_null_max >= observed_global_max))
    global_empirical_p = float((exceedances + 1) / (null_simulations + 1))
    return {
        "status": "engineering_diagnostic",
        "epistemic_class": "UNVERIFIED",
        "claim": "No multiverse or bubble-collision inference is permitted from this pilot.",
        "dataset": {
            "map_url": "https://lambda.gsfc.nasa.gov/data/map/dr5/dfp/ilc/wmap_ilc_9yr_v5.fits",
            "map_sha256": sha256_file(map_path),
            "mask_url": "https://lambda.gsfc.nasa.gov/data/map/dr5/ancillary/masks/wmap_temperature_kq75_analysis_mask_r9_9yr_v5.fits",
            "mask_sha256": sha256_file(mask_path),
            **metadata,
        },
        "pipeline": {
            "lmax": LMAX,
            "beam_fwhm_arcmin": WMAP_BEAM_FWHM_ARCMIN,
            "apodization_deg": APODIZATION_DEG,
            "monopole_dipole": "least-squares fit on KQ75 core, removed before masking",
            "scales_deg": list(SCALES_DEG),
            "null_simulations": null_simulations,
            "seed": seed,
            "trials_scope": "global maximum over all valid pixels and all four scales",
        },
        "global_pilot": {
            "observed_max_sigma": observed_global_max,
            "null_99_percent_threshold_sigma": global_threshold,
            "empirical_p": global_empirical_p,
            "minimum_resolvable_p": 1.0 / (null_simulations + 1),
        },
        "scales": scale_results,
        "fail_closed_flags": [
            "KQ75 core defines searched centers; every reported disk must be at least 80 percent unmasked.",
            "The 128-null ensemble is diagnostic and cannot establish publication-grade tail significance.",
            "Mask-edge leakage remains included in the diagnostic null maximum and can only raise its threshold.",
            "No Planck component-separation, frequency, or polarization holdout has been opened.",
            "Candidates are engineering outputs, not evidence of a multiverse.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("results/wmap-pilot.json"))
    parser.add_argument("--null-simulations", type=int, default=DEFAULT_NULL_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=20260821)
    args = parser.parse_args()
    result = run(args.root, args.null_simulations, args.seed)
    payload = json.dumps(result, indent=2, sort_keys=True)
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
