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
| CMB bubble collisions | azimuthal T/E disk profile | ΛCDM extrema, Galactic foregrounds, beams, masks | WMAP LAMBDA, Planck PLA, healpy, S2FIL, COMB, NaMaster, PySM3 | joint temperature/polarization matched filter with global coverage calibration | 1,000 end-to-end nulls on frozen WMAP pipeline, then approved Planck holdout | all multiverses proven/disproven |
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

### 5. Joint temperature/polarization template matcher

Pre-register a temperature-derived candidate, then test the predicted polarization phase/profile without recentering or retuning. This is the most valuable missing CMB discriminator.

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
