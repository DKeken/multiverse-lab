from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import camb
import numpy as np
from scipy.integrate import simpson
from scipy.special import eval_legendre, roots_legendre, spherical_jn

LMIN = 2
LMAX = 256
SCALE_DEG = 5.0
RADIAL_NODES = 160
ANGULAR_NODES = 96
COSMOLOGY = {
    "H0": 67.5,
    "ombh2": 0.022,
    "omch2": 0.122,
    "tau": 0.06,
    "As": 2.0e-9,
    "ns": 0.965,
}


def transfer_data() -> tuple[Any, Any]:
    parameters = camb.CAMBparams()
    parameters.set_cosmology(
        H0=COSMOLOGY["H0"],
        ombh2=COSMOLOGY["ombh2"],
        omch2=COSMOLOGY["omch2"],
        tau=COSMOLOGY["tau"],
    )
    parameters.InitPower.set_params(As=COSMOLOGY["As"], ns=COSMOLOGY["ns"])
    parameters.set_for_lmax(LMAX, lens_potential_accuracy=0)
    parameters.set_accuracy(lSampleBoost=100)
    data = camb.get_results(parameters)
    return data, data.get_cmb_transfer_data()

def physical_transfers(ell: np.ndarray, delta: np.ndarray) -> np.ndarray:
    normalized = np.array(delta[:2], copy=True)
    e_factor = np.sqrt((np.square(ell) - 1.0) * ell * (ell + 2.0))
    normalized[1] *= e_factor[:, None]
    return normalized


def cl_reconstruction_check(data: Any, transfer: Any) -> dict[str, float]:
    ell = np.asarray(transfer.L)
    q = np.asarray(transfer.q)
    delta = np.asarray(transfer.delta_p_l_k)
    keep = (ell >= LMIN) & (ell <= LMAX)
    ell = ell[keep]
    delta = physical_transfers(ell, delta[:, keep, :])
    primordial = COSMOLOGY["As"] * np.power(q / 0.05, COSMOLOGY["ns"] - 1.0)
    reconstructed = np.empty((ell.size, 3))
    reconstructed[:, 0] = 4.0 * np.pi * simpson(primordial * delta[0] ** 2, x=np.log(q), axis=1)
    reconstructed[:, 1] = 4.0 * np.pi * simpson(primordial * delta[1] ** 2, x=np.log(q), axis=1)
    reconstructed[:, 2] = 4.0 * np.pi * simpson(primordial * delta[0] * delta[1], x=np.log(q), axis=1)
    reference = data.get_unlensed_scalar_cls(lmax=LMAX, raw_cl=True)[ell]
    comparisons = ((0, 0, "tt"), (1, 1, "ee"), (2, 3, "te"))
    errors: dict[str, float] = {}
    for reconstructed_column, reference_column, name in comparisons:
        denominator = np.maximum(np.abs(reference[:, reference_column]), np.max(np.abs(reference[:, reference_column])) * 1e-10)
        relative = np.abs(reconstructed[:, reconstructed_column] - reference[:, reference_column]) / denominator
        errors[f"{name}_median_relative_error"] = float(np.median(relative))
        errors[f"{name}_p95_relative_error"] = float(np.quantile(relative, 0.95))
    return errors


def radial_nodes(x_c: float, x_ls: float, count: int) -> tuple[np.ndarray, np.ndarray]:
    nodes, weights = roots_legendre(count)
    radius = x_c + 0.5 * (nodes + 1.0) * (x_ls - x_c)
    return radius, weights * 0.5 * (x_ls - x_c)


def curvature_l0(
    ell: int,
    radius: np.ndarray,
    x_c: float,
    x_ls: float,
    power: int,
) -> np.ndarray:
    angular_nodes, angular_weights = roots_legendre(ANGULAR_NODES)
    lower = x_c / radius
    mu = lower[:, None] + 0.5 * (angular_nodes[None, :] + 1.0) * (1.0 - lower[:, None])
    weights = angular_weights[None, :] * 0.5 * (1.0 - lower[:, None])
    profile = np.power((radius[:, None] * mu - x_c) / (x_ls - x_c), power)
    angular_integral = np.sum(weights * profile * eval_legendre(ell, mu), axis=1)
    return math.sqrt(math.pi * (2.0 * ell + 1.0)) * angular_integral


def basis_template(
    transfer: Any,
    x_c: float,
    x_ls: float,
    power: int,
    radial_count: int,
) -> dict[str, list[float]]:
    all_ell = np.asarray(transfer.L)
    keep = (all_ell >= LMIN) & (all_ell <= LMAX)
    ell_values = all_ell[keep]
    q = np.asarray(transfer.q)
    delta = physical_transfers(ell_values, np.asarray(transfer.delta_p_l_k)[:, keep, :])
    radius, radius_weights = radial_nodes(x_c, x_ls, radial_count)
    temperature = np.empty(ell_values.size)
    e_mode = np.empty(ell_values.size)
    for index, ell_value in enumerate(ell_values):
        ell = int(ell_value)
        curvature = curvature_l0(ell, radius, x_c, x_ls, power)
        hankel = spherical_jn(ell, q[:, None] * radius[None, :]) @ (
            radius_weights * np.square(radius) * curvature
        )
        kernel = np.square(q) * hankel
        temperature[index] = (2.0 / np.pi) * simpson(kernel * delta[0, index], x=q)
        e_mode[index] = (2.0 / np.pi) * simpson(kernel * delta[1, index], x=q)
    return {
        "ell": ell_values.astype(int).tolist(),
        "temperature_bl0": temperature.tolist(),
        "e_mode_bl0": e_mode.tolist(),
    }


def convergence(reference: dict[str, list[float]], comparison: dict[str, list[float]]) -> dict[str, float]:
    output: dict[str, float] = {}
    for field in ("temperature_bl0", "e_mode_bl0"):
        expected = np.asarray(reference[field])
        actual = np.asarray(comparison[field])
        scale = max(float(np.max(np.abs(expected))), 1e-30)
        output[f"{field}_maximum_absolute_delta_over_peak"] = float(np.max(np.abs(expected - actual)) / scale)
    return output


def information_multipole(ell: np.ndarray, contribution: np.ndarray, fraction: float) -> int:
    cumulative = np.cumsum(contribution)
    if cumulative[-1] <= 0:
        raise RuntimeError("Conditional E information must be positive")
    index = int(np.searchsorted(cumulative, fraction * cumulative[-1], side="left"))
    return int(ell[min(index, ell.size - 1)])


def fisher_information(data: Any, bases: dict[str, dict[str, list[float]]]) -> dict[str, Any]:
    names = ("linear", "quadratic")
    ell = np.asarray(bases[names[0]]["ell"], dtype=int)
    if any(not np.array_equal(ell, np.asarray(bases[name]["ell"], dtype=int)) for name in names[1:]):
        raise RuntimeError("Bubble template bases use inconsistent multipoles")

    scalar_cls = data.get_unlensed_scalar_cls(lmax=int(ell[-1]), raw_cl=True)[ell]
    c_tt = scalar_cls[:, 0]
    c_ee = scalar_cls[:, 1]
    c_te = scalar_cls[:, 3]
    conditional_variance = c_ee - np.square(c_te) / c_tt
    if np.any(c_tt <= 0) or np.any(conditional_variance <= 0):
        raise RuntimeError("CAMB T/E covariance is not positive definite")

    temperature = np.stack([np.asarray(bases[name]["temperature_bl0"]) for name in names])
    e_mode = np.stack([np.asarray(bases[name]["e_mode_bl0"]) for name in names])
    conditional_e = e_mode - temperature * (c_te / c_tt)
    temperature_fisher = (temperature / c_tt) @ temperature.T
    conditional_e_fisher = (conditional_e / conditional_variance) @ conditional_e.T
    joint_fisher = temperature_fisher + conditional_e_fisher

    determinant = c_tt * c_ee - np.square(c_te)
    direct_joint_fisher = np.empty((len(names), len(names)))
    for row in range(len(names)):
        for column in range(len(names)):
            numerator = (
                temperature[row] * temperature[column] * c_ee
                + e_mode[row] * e_mode[column] * c_tt
                - (temperature[row] * e_mode[column] + e_mode[row] * temperature[column]) * c_te
            )
            direct_joint_fisher[row, column] = np.sum(numerator / determinant)
    decomposition_error = float(
        np.max(np.abs(direct_joint_fisher - joint_fisher))
        / max(float(np.max(np.abs(direct_joint_fisher))), 1e-300)
    )
    if decomposition_error > 1e-10:
        raise RuntimeError("Conditional Fisher decomposition does not match direct T/E covariance inversion")

    per_basis: dict[str, dict[str, float | int]] = {}
    for index, name in enumerate(names):
        temperature_value = float(temperature_fisher[index, index])
        conditional_e_value = float(conditional_e_fisher[index, index])
        joint_value = float(joint_fisher[index, index])
        contribution = np.square(conditional_e[index]) / conditional_variance
        per_basis[name] = {
            "temperature_only_fisher": temperature_value,
            "conditional_e_fisher": conditional_e_value,
            "joint_fisher": joint_value,
            "temperature_only_unit_amplitude_sigma": 1.0 / math.sqrt(temperature_value),
            "joint_unit_amplitude_sigma": 1.0 / math.sqrt(joint_value),
            "joint_over_temperature_fisher": joint_value / temperature_value,
            "uncertainty_improvement": math.sqrt(joint_value / temperature_value),
            "conditional_e_fraction_of_joint": conditional_e_value / joint_value,
            "conditional_e_information_ell_50": information_multipole(ell, contribution, 0.5),
            "conditional_e_information_ell_90": information_multipole(ell, contribution, 0.9),
        }

    joint_correlation = float(joint_fisher[0, 1] / math.sqrt(joint_fisher[0, 0] * joint_fisher[1, 1]))
    return {
        "method": "Feeney et al. Eq. 19, exactly decomposed as F_T + F_E_given_T",
        "covariance": "cosmic-variance-only unlensed scalar CAMB TT/EE/TE; no beam, noise, mask, or foreground",
        "basis_order": list(names),
        "temperature_only_matrix": temperature_fisher.tolist(),
        "conditional_e_matrix": conditional_e_fisher.tolist(),
        "joint_matrix": joint_fisher.tolist(),
        "joint_basis_correlation": joint_correlation,
        "joint_matrix_condition_number": float(np.linalg.cond(joint_fisher)),
        "decomposition_maximum_relative_error": decomposition_error,
        "per_basis": per_basis,
    }


def generate() -> dict[str, Any]:
    data, transfer = transfer_data()
    derived = data.get_derived_params()
    x_ls = float(data.comoving_radial_distance(derived["zstar"]))
    x_c = x_ls * math.cos(math.radians(SCALE_DEG))
    transfer_ell = np.asarray(transfer.L)
    dense = bool(np.array_equal(transfer_ell[: LMAX - 1], np.arange(LMIN, LMAX + 1)))
    if not dense:
        raise RuntimeError("CAMB transfer multipoles are not dense through lmax")
    cl_check = cl_reconstruction_check(data, transfer)
    if max(value for key, value in cl_check.items() if "median" in key) > 0.01:
        raise RuntimeError("CAMB transfer normalization did not reconstruct scalar spectra")

    bases: dict[str, dict[str, list[float]]] = {}
    convergence_checks: dict[str, dict[str, float]] = {}
    for power, name in ((1, "linear"), (2, "quadratic")):
        reference = basis_template(transfer, x_c, x_ls, power, RADIAL_NODES)
        comparison = basis_template(transfer, x_c, x_ls, power, RADIAL_NODES // 2)
        bases[name] = reference
        convergence_checks[name] = convergence(reference, comparison)
    converged = max(value for check in convergence_checks.values() for value in check.values()) <= 0.02
    fisher = fisher_information(data, bases)

    return {
        "experiment_id": "physical-bubble-te-template-v1",
        "epistemic_class": "ADAPTED",
        "status": "PASS" if converged else "FAIL",
        "interpretation": "Synthetic unit-curvature T/E basis templates from Feeney et al. Eqs. 1-4 using standard CAMB transfer functions; no observational polarization data were accessed.",
        "geometry": {
            "angular_radius_deg": SCALE_DEG,
            "last_scattering_distance_mpc": x_ls,
            "causal_boundary_distance_mpc": x_c,
            "boundary_shell_width_mpc": x_ls - x_c,
            "profile": "((z-x_c)/(x_ls-x_c))^p Theta(z-x_c), truncated at r=x_ls",
        },
        "engine": {
            "name": "CAMB",
            "version": camb.__version__,
            "cosmology": COSMOLOGY,
            "lmin": LMIN,
            "lmax": LMAX,
            "k_samples": int(np.asarray(transfer.q).size),
            "radial_nodes": RADIAL_NODES,
            "angular_nodes": ANGULAR_NODES,
        },
        "normalization_checks": cl_check,
        "convergence_checks": convergence_checks,
        "fisher_information": fisher,
        "basis_templates": bases,
        "sources": [
            "https://arxiv.org/abs/1506.01716",
            "https://github.com/cmbant/CAMB",
        ],
        "limitations": [
            "Uses public standard CAMB transfer sampling rather than the paper's unreleased modified CAMB and optimized 90-node quadrature.",
            "Truncates the spatial integration at the last-scattering radius.",
            "Unit linear and quadratic curvature bases are not fitted physical amplitudes.",
            "Per-basis diagonal amplitude sigmas hold the other basis fixed; the full matrix shows strong linear/quadratic degeneracy and is not an observational sensitivity.",
            "No beam, mask, instrument noise, foreground, or observational map is applied.",
        ],
        "forbidden_claim": "This template bank is not observational evidence, a detected collision, or proof of a multiverse.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/bubble-te-template.json"))
    args = parser.parse_args()
    result = generate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.write_text(payload)
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "geometry", "normalization_checks", "convergence_checks", "fisher_information")}, indent=2))


if __name__ == "__main__":
    main()
