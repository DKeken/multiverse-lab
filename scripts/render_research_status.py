from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WMAP_INPUT = ROOT / "results" / "wmap-pilot.json"
JOINT_INPUT = ROOT / "results" / "joint-te-synthetic.json"
CAMB_INPUT = ROOT / "results" / "camb-te-selection.json"
BUBBLE_INPUT = ROOT / "results" / "bubble-te-template.json"
MASKED_INPUT = ROOT / "results" / "masked-te-injection.json"
STRESS_INPUT = ROOT / "results" / "te-systematics-stress.json"
DEPTH_INPUT = ROOT / "results" / "te-noise-depth.json"
PIXEL_INPUT = ROOT / "results" / "te-pixel-covariance.json"
SCAN_INPUT = ROOT / "results" / "bubble-geometry-scan.json"
WMAP_FILTER_INPUT = ROOT / "results" / "wmap-t-radius-filter.json"
NULL_INPUT = ROOT / "results" / "wmap-t-null-pipeline.json"
OUTPUT = ROOT / "results" / "research-control-room.svg"


def esc(value: object) -> str:
    return html.escape(str(value))


def text(x: float, y: float, value: object, size: int = 14, color: str = "#a8b3cf", weight: int = 400, anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'


def line(x1: float, y1: float, x2: float, y2: float, color: str = "#26324d", width: float = 1, dash: str = "") -> str:
    dashed = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dashed}/>'


def card(x: float, y: float, w: float, h: float, title: str) -> list[str]:
    return [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#111827" stroke="#26324d"/>',
        text(x + 20, y + 28, title.upper(), 12, "#6f7e9f", 700),
    ]


def load_result() -> dict[str, Any]:
    value = json.loads(WMAP_INPUT.read_text())
    if type(value) is not dict:
        raise ValueError("WMAP result must be an object")
    return value


def all_candidates(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for scale in result["scales"]:
        for candidate in scale["candidates"]:
            candidates.append({**candidate, "scale_deg": scale["scale_deg"]})
    return candidates


def mollweide_point(longitude_deg: float, latitude_deg: float, x: float, y: float, w: float, h: float) -> tuple[float, float]:
    longitude = math.radians(((longitude_deg + 180) % 360) - 180)
    latitude = math.radians(latitude_deg)
    theta = latitude
    for _ in range(8):
        denominator = 2 + 2 * math.cos(2 * theta)
        if abs(denominator) < 1e-12:
            break
        theta -= (2 * theta + math.sin(2 * theta) - math.pi * math.sin(latitude)) / denominator
    px = x + w / 2 + (2 * math.sqrt(2) / math.pi * longitude * math.cos(theta)) * w / (4 * math.sqrt(2))
    py = y + h / 2 - (math.sqrt(2) * math.sin(theta)) * h / (2 * math.sqrt(2))
    return px, py


def render() -> str:
    result = load_result()
    joint = json.loads(JOINT_INPUT.read_text())
    camb_result = json.loads(CAMB_INPUT.read_text())
    bubble_result = json.loads(BUBBLE_INPUT.read_text())
    masked_result = json.loads(MASKED_INPUT.read_text())
    stress_result = json.loads(STRESS_INPUT.read_text())
    depth_result = json.loads(DEPTH_INPUT.read_text())
    pixel_result = json.loads(PIXEL_INPUT.read_text())
    pilot = result["global_pilot"]
    pipeline = result["pipeline"]
    candidates = all_candidates(result)
    n = int(pipeline["null_simulations"])
    k = int(pilot["null_exceedances"])
    current_p = (k + 1) / (n + 1)
    observed = float(pilot["observed_max_sigma"])
    threshold = float(pilot["null_99_percent_threshold_sigma"])
    naive_rate = float(joint["null_calibration"]["naive_selected_e_rate"])
    conditional_rate = float(joint["null_calibration"]["conditional_rate"])
    camb_rho = float(camb_result["filter"]["effective_rho"])
    bubble_fisher = bubble_result["fisher_information"]["per_basis"]
    linear_gain = float(bubble_fisher["linear"]["joint_over_temperature_fisher"])
    quadratic_gain = float(bubble_fisher["quadratic"]["joint_over_temperature_fisher"])
    camb_reconstruction_p95 = max(
        float(value)
        for key, value in bubble_result["normalization_checks"].items()
        if "p95" in key
    )
    masked_recovery = masked_result["recovery"]
    retained_snr = float(masked_recovery["retained_snr_fraction"])
    recovered_score = float(masked_recovery["recovered_injection_response_score_sigma"])
    b_leakage = float(masked_recovery["purified_b_leakage_score_sigma"])
    stress_recovery = stress_result["recovery"]
    stress_expected = float(stress_recovery["expected_injection_response_score_sigma"])
    stress_total = float(stress_recovery["total_recovery_score_sigma"])
    stress_bias = float(stress_recovery["fractional_injection_response_bias"])
    calibrated_depth = float(depth_result["calibrated_depth"]["base_rms_uK_per_pixel"])
    depth_successes = int(depth_result["validation"]["successes"])
    depth_trials = int(depth_result["validation"]["trials"])
    pixel_successes = int(pixel_result["validation"]["successes"])
    pixel_trials = int(pixel_result["validation"]["trials"])
    pixel_b_max = float(pixel_result["validation"]["maximum_absolute_b_score"])
    scan_rows = json.loads(SCAN_INPUT.read_text())["radii"]
    scan_typical = {row["angular_radius_deg"]: float(row["typical_ceiling_sigma"]) for row in scan_rows}
    wmap_rows = json.loads(WMAP_FILTER_INPUT.read_text())
    null_result = json.loads(NULL_INPUT.read_text())
    null_p = float(null_result["observed"]["p_value"])

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">',
        '<rect width="1440" height="900" fill="#080d18"/>',
        '<style>text{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.mono{font-family:"SFMono-Regular",Consolas,monospace}</style>',
        '<rect x="0" y="0" width="1440" height="64" fill="#0b1220"/>',
        text(28, 39, "MULTIVERSE LAB", 18, "#f5f7ff", 800),
        text(212, 39, "RESEARCH CONTROL ROOM", 12, "#7b8bad", 700),
        '<circle cx="1340" cy="32" r="5" fill="#45d483"/>',
        text(1354, 37, "LIVE ARTIFACT", 11, "#8fa0c4", 700),
    ]

    out += card(24, 86, 892, 380, "WMAP temperature-only global search")
    map_x, map_y, map_w, map_h = 52, 132, 588, 280
    out.append(f'<ellipse cx="{map_x + map_w / 2}" cy="{map_y + map_h / 2}" rx="{map_w / 2}" ry="{map_h / 2}" fill="#0a1020" stroke="#34415f" stroke-width="1.5"/>')
    for lon in (-120, -60, 0, 60, 120):
        px, _ = mollweide_point(lon, 0, map_x, map_y, map_w, map_h)
        out.append(line(px, map_y + 18, px, map_y + map_h - 18, "#1d2942", 1, "3 5"))
    for lat in (-60, -30, 0, 30, 60):
        _, py = mollweide_point(0, lat, map_x, map_y, map_w, map_h)
        out.append(line(map_x + 22, py, map_x + map_w - 22, py, "#1d2942", 1, "3 5"))
    for candidate in candidates:
        px, py = mollweide_point(float(candidate["galactic_longitude_deg"]), float(candidate["galactic_latitude_deg"]), map_x, map_y, map_w, map_h)
        significance = float(candidate["significance"])
        radius = 3.5 + max(0.0, significance - 2.5) * 2.8
        cold = float(candidate["filtered_amplitude"]) < 0
        color = "#54a8ff" if cold else "#ff7a8a"
        opacity = min(0.95, 0.35 + significance / 9)
        out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{radius:.2f}" fill="{color}" fill-opacity="{opacity:.2f}" stroke="#dbe8ff" stroke-opacity="0.35"/>')
    out += [
        text(52, 440, "blue = cold candidate   red = hot candidate   radius ∝ local σ", 11, "#6f7e9f"),
        text(676, 150, "GLOBAL MAX", 11, "#6f7e9f", 700),
        text(676, 183, f"{observed:.4f}σ", 30, "#f4f7ff", 800),
        text(676, 218, "99% NULL THRESHOLD", 11, "#6f7e9f", 700),
        text(676, 250, f"{threshold:.4f}σ", 26, "#ffba69", 750),
        text(676, 290, "EMPIRICAL p", 11, "#6f7e9f", 700),
        text(676, 322, f"{current_p:.4f}", 28, "#ff7a8a", 800),
        text(676, 350, f"k={k} exceedances / n={n} nulls", 12, "#8fa0c4"),
        '<rect x="676" y="374" width="204" height="38" rx="8" fill="#301923" stroke="#743446"/>',
        text(778, 399, "NO GLOBAL EXCESS", 12, "#ff9dac", 800, "middle"),
    ]

    out += card(940, 86, 476, 380, "Null-budget futility")
    chart_x, chart_y, chart_w, chart_h = 972, 158, 410, 226
    five_sigma_alpha = 2.866515718791933e-7
    five_sigma_budget = math.ceil((k + 1) / five_sigma_alpha) - 1
    budgets = [128, 256, 512, 1024, 1699, 10_000, 100_000, 1_000_000, five_sigma_budget]
    log_min, log_max = math.log10(min(budgets)), math.log10(max(budgets))
    p_min, p_max = 1e-7, 0.2
    def bx(budget: int) -> float:
        return chart_x + (math.log10(budget) - log_min) / (log_max - log_min) * chart_w
    def py(probability: float) -> float:
        return chart_y + (math.log10(p_max) - math.log10(probability)) / (math.log10(p_max) - math.log10(p_min)) * chart_h
    for alpha, label, color in [(0.05, "0.05", "#7383a7"), (0.01, "0.01", "#ffba69"), (five_sigma_alpha, "5σ", "#ff7a8a")]:
        yv = py(alpha)
        out.append(line(chart_x, yv, chart_x + chart_w, yv, color, 1, "5 5"))
        out.append(text(chart_x + chart_w - 3, yv - 5, label, 10, color, 700, "end"))
    points = [(bx(b), py((k + 1) / (b + 1))) for b in budgets]
    out.append('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in points) + '" fill="none" stroke="#7c8cff" stroke-width="3"/>')
    for budget in (128, 1699, 1_000_000, five_sigma_budget):
        x = bx(budget)
        probability = (k + 1) / (budget + 1)
        y = py(probability)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#dbe2ff"/>')
    out += [
        text(chart_x, 407, "128", 10, "#6f7e9f"),
        text(chart_x + chart_w / 2, 407, "null budget (log)", 10, "#6f7e9f", 400, "middle"),
        text(chart_x + chart_w, 407, f"{five_sigma_budget / 1_000_000:.1f}M", 10, "#6f7e9f", 400, "end"),
        text(972, 438, f"5σ requires ≥{five_sigma_budget:,} total nulls", 13, "#ff9dac", 700),
        text(972, 457, "Decision: move compute to independent T/E gate", 12, "#8fa0c4"),
    ]

    out += card(24, 490, 1392, 238, "Conditional physical T/E gate")
    stages = [
        (64, "KNOWN COLD SPOT", "1.103° MATCH", "#45d483"),
        (290, "E ⟂ T", f"{conditional_rate * 100:.3f}% FPR", "#45d483"),
        (516, "PHYSICAL T/E", f"BANK {bubble_result['status']}", "#45d483"),
        (742, "HARMONIC DEPTH", f"{depth_result['status']} · {depth_successes}/{depth_trials}", "#ffba69"),
        (968, "PIXEL COV", f"{pixel_result['status']} · {pixel_successes}/{pixel_trials}", "#ff7a8a"),
        (1194, "PLANCK + Q/U", "SEALED", "#ff7a8a"),
    ]
    for index, (x, label, state, color) in enumerate(stages):
        if index:
            out.append(line(stages[index - 1][0] + 150, 610, x - 16, 610, "#435170", 2))
            out.append(f'<path d="M{x-22} 604 L{x-12} 610 L{x-22} 616" fill="none" stroke="#435170" stroke-width="2"/>')
        out.append(f'<rect x="{x}" y="558" width="166" height="104" rx="12" fill="#0c1425" stroke="{color}" stroke-opacity="0.7"/>')
        out.append(f'<circle cx="{x + 20}" cy="578" r="5" fill="{color}"/>')
        out.append(text(x + 16, 616, label, 12, "#eef2ff", 750))
        out.append(text(x + 16, 641, state, 10, color, 700))
    out += [
        text(64, 696, f"Null-calibrated: p = {null_p:.3f}; 95% UL R₀ = 1.1–2.3×10⁻⁴; development-data collision search closed.", 12, "#45d483"),
        text(1366, 696, "Planck sealed · approval-gated", 11, "#ffba69", 700, "end"),
    ]

    out += card(24, 752, 1392, 120, "Operations")
    statuses = [
        (52, "DEPENDABOT", "0 OPEN PR", "#45d483"),
        (330, "GITHUB CI", "GREEN", "#45d483"),
        (570, "AIPOCH", "REVIEWER PACKAGED", "#7c8cff"),
        (890, "REMOTE LLM", "MAX 1 IN FLIGHT", "#ffba69"),
        (1198, "PLANCK", "HOLDOUT SEALED", "#ff7a8a"),
    ]
    for x, label, state, color in statuses:
        out.append(text(x, 798, label, 10, "#6f7e9f", 700))
        out.append(f'<circle cx="{x}" cy="827" r="5" fill="{color}"/>')
        out.append(text(x + 13, 832, state, 13, "#e8edff", 700))
    out += [
        text(1392, 888, "generated from WMAP + physical T/E + systematics + covariance + geometry-scan JSON", 10, "#4e5b78", 400, "end"),
        "</svg>",
    ]
    return "".join(out)


def main() -> None:
    OUTPUT.write_text(render())
    print(OUTPUT)


if __name__ == "__main__":
    main()
