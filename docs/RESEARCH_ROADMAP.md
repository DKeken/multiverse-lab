# Research roadmap

## Goal hierarchy

1. Discover a reproducible observable that discriminates a named model from conventional rivals.
2. Replicate it with an independent instrument or experiment under a frozen analysis.
3. Determine whether the inferred structure is causally accessible.
4. Define an operational destination variable.
5. Only then assess channel creation and engineering.

Current work is on step 1. Portal engineering is not assessable yet.

## Tracks

| Track | Observable | Strong rivals | Ready data/code | Missing invention | Cheapest next gate | Forbidden conclusion |
|---|---|---|---|---|---|---|
| CMB bubble collisions | conditional T/E disk template with B/foreground vetoes | ΛCDM extrema, Galactic foregrounds, beams, masks, T-selection bias | WMAP LAMBDA, healpy/ducc0, S2FIL, COMB, CAMB, NaMaster, PySM3 | public covariance-aware observational joint T/E pipeline with nuisance projection | replace synthetic covariance with physical CAMB template/covariance; calibrate injections before approved holdout | all multiverses proven/disproven |
| Cosmic topology | matched circles; off-diagonal harmonic covariance | mask/scan coupling, foregrounds, chance circle pairs | Planck maps/masks, HEALPix, topology literature | scalable joint circle+covariance statistic with empirical trials | injection recovery on compact-topology simulations | topology implies another accessible universe |
| Stochastic GW backgrounds | spectral shape, anisotropy, polarization | compact binaries, phase transitions, instrument correlations | LVK open data, PTAs, `bilby`, `enterprise`, `pygwb` | model-family discriminator robust to astrophysical population uncertainty | public injection challenge with frozen rivals | unexplained background proves multiverse |
| Objective collapse | mass/time-dependent decoherence beyond environmental model | vibration, thermal, electromagnetic decoherence | matter-wave/optomechanics publications, QuTiP | experiment-specific nuisance-complete simulator and calibrated likelihood | reproduce published exclusion curves | Bell/quantum eraser proves branching |
| Analogue gravity | mode conversion/correlations in controlled media | ordinary dispersion, heating, detector coupling | BEC/optical experiment data where public, QuTiP/custom simulators | cross-platform dimensionless invariant linking analogue regimes | reproduce one published spectrum from raw public data | analogue horizon is spacetime wormhole |
| Wormhole consistency | throat, horizons, stress tensor, QEI, tides, stability | coordinate artifacts, modified-gravity bookkeeping, invalid semiclassical approximation | SymPy, official Wolfram, xAct literature | restricted metric IR plus perturbation/backreaction certificates | machine-check Morris–Thorne families and known counterexamples | consistent equations imply construction/existence |

## Primary inventions

### 1. Scientific hypothesis IR and compiler

A safe intermediate representation that binds equations, symbols, exact dimensions, domains, assumptions, observable, falsifier, rivals, cost, and epistemic status. It must compile independently to SymPy and Wolfram without arbitrary parsing.

### 2. Cross-CAS evidence gate

A provenance-preserving agreement protocol—not majority voting. Same normalized assumptions and expression go to independent engines. Disagreement produces a terminal quarantine artifact with a minimal counterexample search.

### 3. Multifidelity information scheduler

Choose the cheapest decisive falsifier using expected information per constrained cost. Maintain quality-diversity niches so novelty survives without allowing fitness to override hard scientific failures.

### 4. Globally calibrated spherical anomaly detector

One pipeline for masks, beams, component separation, scale/position/sign trials, injection coverage, end-to-end nulls, and independent T/E holdouts. Output calibrated candidate ledgers, never “discoveries.”

### 5. Conditional joint temperature/polarization matcher

Published Cold Spot work already tested fixed-coordinate radial `Qr/Ur`; temperature-only all-sky bubble filters and theoretical joint T/E forecasts also exist. The missing open implementation is narrower: condition polarization on the temperature used for candidate selection,

$$E_{\perp T}=E-C_{ET}C_{TT}^{-1}T,$$

then project frozen leakage/foreground nuisance modes and reserve B for a veto. Synthetic calibration at 256 temperature trials per sky inflated a naive nominal one-sided `z≥3` E confirmation from the Gaussian `0.135%` target to `13.684%`; the conditional statistic returned `0.195%`, calibrated mean/std, nuisance invariance, and injection recovery. This is an adapted method result, not observational evidence.

Physical-template gate: a repository-owned adapter now propagates five-degree unit-linear and unit-quadratic Feeney Eq. 1-4 curvature profiles through pinned CAMB 2.0.3 T/E transfer functions. Independent TT/EE/TE reconstruction has p95 relative error below `0.078%`, and radial convergence drift is below `3.6e-13` of peak. Eq. 19 gives joint-over-temperature information ratios `1.740` (linear) and `1.607` (quadratic), with strong basis correlation `0.964`. These are cosmic-variance-only, fixed-other-basis synthetic forecasts—not observational evidence.

Masked-injection gate: the frozen `NSIDE=64`, `lmax=96` linear template was injected at `5σ` into synthetic correlated T/Q/U, then passed through a 20-degree Galactic cut, 5-degree C2 apodization, NaMaster pure E/B, and exact 100 GHz PySM3 d1+s1 nuisance deprojection. The processed template retained `99.969%` of full-sky conditional-E S/N; recovered response was `4.99846σ`, B leakage `1.66e-5σ`, and exact-template foreground delta `4.04e-16σ`. This validates mask/purification/projection mechanics only.

Systematic-mismatch gate: a preregistered adversarial scenario replaced truth with PySM3 d2+s2 at 105 GHz while fitting d1+s1 at 100 GHz, mismatched 60/55-arcmin beams, and applied 1% gain, 0.5-degree angle error, and anisotropic `2–6 µK/pixel` Q/U noise. The gate **failed**: expected response fell to `0.926σ` and the frozen realization totaled `−0.739σ`, below the `3σ` threshold. Injection-response bias remained `0.392%`, foreground residual `−0.045σ`, and B score `−0.00428σ`; noise depth is the active blocker in this scenario. Next gate: derive a frozen noise-depth requirement and then calibrate it across independent seeds before any observational polarization access.

Noise-depth gate: an analytic Gaussian matched-filter forecast fixed the mean score at `4.28155σ`, required for 90% probability of exceeding `3σ`, and solved a maximum base Q/U noise of `0.192293 µK/pixel` under the inherited one-to-three anisotropic depth pattern (`0.576878 µK/pixel` maximum). This is `10.4×` deeper than the failed stress input. Validation passed exactly at the preregistered boundary: `58/64 = 90.625%` independent harmonic CMB+noise seeds exceeded `3σ`, with mean `4.260σ`, sample standard deviation `0.903`, and minimum `2.554σ`. This is a fragile finite synthetic calibration, not a lower confidence bound on 90% power or a statement about Planck. Next gate: replace mean-noise harmonic covariance with the full anisotropic pixel/cut-sky covariance and repeat power calibration before observational polarization access.

Pixel-covariance gate: the harmonic depth was tested unchanged using a matrix-free `65024 × 65024` cut-sky Q/U covariance with exact inherited anisotropic pixel-noise variance, CAMB conditional-E signal covariance, and d1+s1 nuisance projection in the same inverse metric. All six CG solves converged in `99–124` iterations with maximum relative residual `9.42e-8`, but the gate **failed**: only `55/64 = 85.94%` seeds exceeded `3σ` versus the frozen `58/64`, mean E score was `3.990σ`, and maximum absolute B score was `3.601σ` versus the `3σ` veto. Therefore `0.192293 µK/pixel` is rejected as a robust target under the more exact covariance. Next gate: preregister and solve a stricter depth using this matrix-free operator, then validate on a fresh seed block; no post-hoc reuse of these seeds.

Instrument-feasibility verdict (stop rule): the frozen requirement is base Q/U noise at or below roughly `0.19 µK/pixel` at `NSIDE=64`, equivalent to polarization map depth of order `10 µK·arcmin`. Published Planck HFI polarization depths are order `600–1000 µK·arcmin` per channel; even an optimistic `100+143+217 GHz` combination is at least `30×` short, and WMAP polarization is worse. CMB-S4-class targets of `1–2 µK·arcmin` give `5–10×` margin. Therefore Planck Q/U is declared non-viable for this statistic at the frozen unit-basis `5σ` amplitude, the holdout polarization tier stays closed, and the synthetic depth-calibration series stops. Sensitivity figures are order-of-magnitude `[INFERENCE]` from the Planck Blue Book and 2018 overview and must be pinned to the primary paper before any future holdout decision. The requirement is conditional on the arbitrary unit-basis injection amplitude; deriving a physically motivated amplitude prior is the next scientific input.

Physical-amplitude closure: the repository unit bases match the published Feeney $\mathcal R_0$ normalizations exactly (arXiv:1506.01716 Eqs. 15–17), so the stored `2.64×10⁻³` injection equals $\mathcal R_0$ and sat `1.94×` above the fiducial linear maximum ($\delta\phi_0/M_{\rm Pl}=1$, $1-\cos\Delta x=2$, $r=0.1$, $\Omega_k=10^{-4}$) and `2.3×10⁵×` above the quadratic maximum. Cosmic-variance ceilings at this geometry: quadratic `2.1×10⁻⁵σ` — permanently unobservable; typical linear amplitudes (`δφ₀/M_Pl = 0.01–0.1`) `0.02–0.20σ`; only the extreme Planckian corner reaches `3.99σ` with a perfect noise-free full-sky experiment, and every realistic instrument is ≥5× too shallow for it. The conditional T/E program at the five-degree Cold Spot geometry is therefore closed as a forecast no-go. Any revival must change geometry or observable and recompute the mapping in [`research/bubble-amplitude-prior.yml`](../research/bubble-amplitude-prior.yml); WMAP7 and Planck searches remain the observational authority on bubble collisions.

Geometry scan (revival found): a nine-radius cosmic-variance Fisher survey over the same CAMB pipeline shows the five-degree closure is geometry-specific. Joint-linear $\sigma$ falls `3.42×10⁻⁴ → 4.32×10⁻⁵` from `5°` to `60°` while the fiducial physical maximum $\mathcal R_0^L\propto(x_{ls}-x_c)/x_{ls}$ grows `131×`, so perfect-experiment ceilings rise `3.99σ → 4145σ`. Typical physical amplitudes (`δφ₀/M_Pl = 0.1`, unit separation factor) reach `3.38σ` at `10°` and `11.4–207σ` at `15–60°`. Large-radius templates are low-$\ell$ dominated — exactly where Planck/WMAP temperature maps sit nearest cosmic variance — so the next gate is a preregistered analytic-threshold multi-radius temperature matched filter on development WMAP data (no Monte-Carlo null wall, no holdout access), with any Planck extension remaining approval-gated. Ceilings are lower bounds (`ℓ ≤ 256` truncation) and are not expectations; published searches already exclude part of this parameter space.

WMAP temperature screen (first development-data result): an analytic multi-radius matched filter (`10/15/20/30°`, `|b|≥20°` cut, pseudo-`C_ℓ`, cosmic-variance TT covariance) on the WMAP ILC 9-year map finds **no excess**: all pre-trials `|z|<1` (`−0.55…+0.99`). It delivers 95% upper limits `R_0^L = 1.09–2.23×10⁻⁴` across radii — `4.4–29×` below typical physical amplitudes at `15–30°`, constraining `δφ₀/M_Pl × (1−cosΔx)` at the few-`10⁻³` level. The post-trials column subtracts the independent-lobe penalty from signed `z` and is only meaningful for positive excursions; nothing approaches it. Any future excess must survive a frozen end-to-end null pipeline; Planck remains sealed and approval-gated.

Null-calibrated closure: an end-to-end pipeline (ud-grade to `NSIDE=256`, `|b|≥20°` mask, zero-iteration harmonics, identical scoring) run on `1000` Gaussian skies calibrates the observed maximum `z = 0.994` at **`p = 0.417`** — the WMAP-T no-detection is fully calibrated. Empirical 95% limits `R_0^L = 1.08–2.29×10⁻⁴` match the analytic screen within a few percent, confirming mask coupling is negligible at these radii. The development-data bubble-collision screen is closed: no excess, calibrated limits delivered. Next observational steps require Planck approval (holdout) or a different observable; synthetic-method work continues only where it changes a decision.

Analytic-null invention (Monte Carlo deleted for this class): because the multi-radius filter is linear and the sky model Gaussian, its full null distribution is closed-form — Legendre moments `g_{rL}` of each masked filter kernel give `Var(s_r)=4πΣ_L C_L W_L²g²/(2L+1)` and the joint `z` covariance, so p-values need zero simulations. Validation: fresh-null correlations reproduce to `0.027` max deviation after adding the pixel window (`W_256≈0.54`), and the analytic `p=0.4022` matches the thousand-sky `0.4166`. The frozen diagonal check fails formally at one radius (`5.26%` vs `5%`, i.e. `2.3σ` of the reference's own MC error); artifact stays INVALID, no retroactive threshold change. Runtime: seconds versus 103 s of nulls — and exact. This is the x1000-class method export: any linear Gaussian matched-filter pipeline inherits it.

## Dataset strategy

Do not mirror large datasets. Registry entries must freeze URL, SHA-256, byte size, release, license/terms, field/order/unit semantics, role (`development`, `calibration`, `holdout`), redistribution status, and cache path.

Preferred authorities:

- NASA LAMBDA: WMAP maps, masks, likelihood products.
- ESA Planck Legacy Archive: component maps, frequency maps, masks, FFP simulations.
- GWOSC: calibrated LVK strain and event products.
- NANOGrav/EPTA/PPTA/IPTA official releases: pulsar timing products.
- NASA ADS, arXiv, INSPIRE: literature metadata; paper claims still require primary-source reading.

## Evidence ladder

```text
schema → local math → independent CAS → toy simulation
→ injection recovery → public development data
→ foreground/systematics vetoes → frozen independent holdout
→ external replication
```

A failure at any rung is useful evidence and enters the failure-signature archive.

## Stop rules

- No expensive simulation before a cheap mathematical survivor exists.
- No neural posterior before simulator coverage is measured.
- No holdout access before thresholds, trials, coordinates, scales, and vetoes are frozen.
- No new abstraction until two consumers require it.
- No hardware proposal before target existence and causal accessibility are established.
