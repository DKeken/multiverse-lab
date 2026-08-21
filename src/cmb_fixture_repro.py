from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import healpy as hp
import numpy as np

NSIDE = 128
LMAX = 256
SCALES_DEG = (5.0, 10.0, 20.0, 30.0)
SOURCE_RADIUS_DEG = 3.0
FALSE_PEAK_BUDGET = 2


@dataclass(frozen=True)
class Source:
    amplitude: float
    phi: float
    theta: float


@dataclass(frozen=True)
class Peak:
    pixel: int
    theta: float
    phi: float
    significance: float
    filtered_amplitude: float


def load_truth(path: Path) -> list[Source]:
    sources: list[Source] = []
    current: dict[str, float] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("object"):
            if current:
                sources.append(Source(**current))
                current = {}
        elif line.startswith("amplitude"):
            current["amplitude"] = float(line.split("=", 1)[1])
        elif line.startswith("alpha"):
            current["phi"] = float(line.split("=", 1)[1])
        elif line.startswith("beta"):
            current["theta"] = float(line.split("=", 1)[1])
    if current:
        sources.append(Source(**current))
    return sources


def bubble_template(scale_deg: float) -> np.ndarray:
    """Exact continuous COMB bubble profile used by the fixture generator."""
    theta, _ = hp.pix2ang(NSIDE, np.arange(hp.nside2npix(NSIDE)))
    theta_c = math.radians(scale_deg)
    theta_0 = 1.1 * theta_c
    z0 = 1.0
    zc = 0.2
    c1 = (z0 - zc) / (1.0 - math.cos(theta_c))
    c0 = z0 - c1
    profile = c0 + c1 * np.cos(theta)
    taper = np.zeros_like(theta)
    taper[theta < theta_c] = 1.0
    transition = (theta >= theta_c) & (theta <= theta_0)
    ts = (theta[transition] - theta_c) / (theta_0 - theta_c)
    taper[transition] = np.exp(-1.0 / (1.0 - np.square(ts))) * math.e
    return profile * taper


def theory_background_cl(
    path: Path,
    noise_std: float,
    *,
    beam_fwhm_arcmin: float = 13.2,
    output_unit: str = "mK",
) -> np.ndarray:
    if output_unit not in {"mK", "K"}:
        raise ValueError("output_unit must be 'mK' or 'K'")
    microkelvin2_divisor = 1_000_000.0 if output_unit == "mK" else 1_000_000_000_000.0
    table = np.loadtxt(path)
    ell = table[:, 0].astype(int)
    dl_tt_microkelvin2 = table[:, 1]
    cl = np.full(LMAX + 1, np.inf)
    valid = (ell >= 2) & (ell <= LMAX)
    selected_ell = ell[valid]
    cmb_cl = (
        2.0
        * np.pi
        * dl_tt_microkelvin2[valid]
        / (selected_ell * (selected_ell + 1.0))
        / microkelvin2_divisor
    )
    beam = hp.gauss_beam(math.radians(beam_fwhm_arcmin / 60.0), lmax=LMAX)
    cl[selected_ell] = cmb_cl * np.square(beam[selected_ell])
    white_noise_cl = 4.0 * np.pi * noise_std**2 / hp.nside2npix(NSIDE)
    cl[2:] += white_noise_cl
    return cl


def matched_filter_transfer(
    template: np.ndarray,
    background_cl: np.ndarray,
    *,
    beam_fwhm_arcmin: float = 13.2,
) -> np.ndarray:
    """Axisymmetric matched filter from McEwen et al. Eq. (5) and S2FIL."""
    tau_alm = hp.map2alm(template, lmax=LMAX, mmax=0, iter=3)
    beam = hp.gauss_beam(math.radians(beam_fwhm_arcmin / 60.0), lmax=LMAX)
    tau_l0 = tau_alm.real * beam
    alpha = np.sum(np.square(np.abs(tau_l0[2:])) / background_cl[2:])
    psi_l0 = np.zeros(LMAX + 1)
    psi_l0[2:] = tau_l0[2:] / (alpha * background_cl[2:])
    ell = np.arange(LMAX + 1)
    return np.sqrt(4.0 * np.pi / (2.0 * ell + 1.0)) * psi_l0


def filter_alm(sky_alm: np.ndarray, transfer: np.ndarray) -> np.ndarray:
    return hp.alm2map(hp.almxfl(sky_alm, transfer), NSIDE, lmax=LMAX)


def separated_peaks(
    values: np.ndarray,
    separation_deg: float,
    *,
    min_significance: float = 0.0,
    max_count: int | None = None,
) -> list[Peak]:
    order = np.argsort(np.abs(values))[::-1]
    selected: list[Peak] = []
    min_separation = math.radians(separation_deg)
    for pixel in order:
        significance = float(abs(values[pixel]))
        if significance <= min_significance:
            break
        theta, phi = hp.pix2ang(NSIDE, int(pixel))
        vector = hp.ang2vec(theta, phi)
        if any(
            hp.rotator.angdist(vector, hp.ang2vec(peak.theta, peak.phi))[0]
            < min_separation
            for peak in selected
        ):
            continue
        selected.append(
            Peak(
                pixel=int(pixel),
                theta=float(theta),
                phi=float(phi),
                significance=significance,
                filtered_amplitude=float(values[pixel]),
            )
        )
        if max_count is not None and len(selected) >= max_count:
            break
    return selected


def nearest_truth_distance_deg(peak: Peak, truth: list[Source]) -> tuple[int, float]:
    distances = [
        math.degrees(
            hp.rotator.angdist(
                hp.ang2vec(peak.theta, peak.phi), hp.ang2vec(source.theta, source.phi)
            )[0]
        )
        for source in truth
    ]
    index = int(np.argmin(distances))
    return index, float(distances[index])


def run(root: Path) -> dict[str, object]:
    fixture = root / "vendor" / "s2fil" / "data_in"
    signal = hp.read_map(fixture / "bubble_obj.fits")
    cmb = hp.read_map(fixture / "bubble_cmb.fits")
    noise = hp.read_map(fixture / "bubble_wnoise.fits")
    injected = hp.read_map(fixture / "bubble_csky.fits")
    null = cmb + noise
    closure = float(np.max(np.abs(injected - null - signal)))
    truth = load_truth(fixture / "bubble_param_out.par")
    background_cl = theory_background_cl(
        fixture / "wmap_lcdm_pl_model_wmap7baoh0_CAMB.dat",
        noise_std=float(np.std(noise)),
    )
    null_alm = hp.map2alm(null, lmax=LMAX, iter=3)
    injected_alm = hp.map2alm(injected, lmax=LMAX, iter=3)

    scale_results: list[dict[str, object]] = []
    recovered_truth: set[int] = set()
    for scale_deg in SCALES_DEG:
        transfer = matched_filter_transfer(bubble_template(scale_deg), background_cl)
        filtered_null = filter_alm(null_alm, transfer)
        filtered_injected = filter_alm(injected_alm, transfer)
        null_mean = float(np.mean(filtered_null))
        null_std = float(np.std(filtered_null))
        null_significance = (filtered_null - null_mean) / null_std
        injected_significance = (filtered_injected - null_mean) / null_std

        null_peaks = separated_peaks(
            null_significance,
            separation_deg=scale_deg,
            max_count=FALSE_PEAK_BUDGET + 1,
        )
        threshold = float(null_peaks[FALSE_PEAK_BUDGET].significance)
        candidate_peaks = separated_peaks(
            injected_significance,
            separation_deg=scale_deg,
            min_significance=threshold,
        )
        matches: list[dict[str, object]] = []
        for peak in candidate_peaks:
            truth_index, distance_deg = nearest_truth_distance_deg(peak, truth)
            is_match = distance_deg <= SOURCE_RADIUS_DEG
            if is_match:
                recovered_truth.add(truth_index)
            matches.append(
                {
                    **asdict(peak),
                    "truth_index": truth_index,
                    "distance_deg": distance_deg,
                    "matched": is_match,
                }
            )
        scale_results.append(
            {
                "scale_deg": scale_deg,
                "threshold": threshold,
                "null_false_peaks": sum(
                    peak.significance > threshold for peak in null_peaks
                ),
                "candidate_count": len(candidate_peaks),
                "matches": matches,
            }
        )

    return {
        "status": "modern-backend fixture reproduction",
        "reference": "https://github.com/astro-informatics/s2fil",
        "paper": "https://arxiv.org/abs/1202.2861",
        "backend": {"healpy": hp.__version__, "nside": NSIDE, "lmax": LMAX},
        "fixture_closure_max_abs": closure,
        "truth_count": len(truth),
        "recovered_truth_indices": sorted(recovered_truth),
        "recovered_truth_count": len(recovered_truth),
        "all_truth_recovered": len(recovered_truth) == len(truth),
        "false_peak_budget_per_scale": FALSE_PEAK_BUDGET,
        "scales": scale_results,
        "limitations": [
            "Uses modern healpy/ducc0 transforms rather than the unrebuildable legacy S2/FastCSWT stack.",
            "Uses the exact continuous COMB generator profile z0=1, zc=0.2 and theta0=1.1*theta_c.",
            "One supplied null realization calibrates thresholds; this is fixture sensitivity measurement, not publication-grade significance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.root)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
