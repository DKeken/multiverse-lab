# Hallucination-to-Hypothesis Compiler

## Decision

LLM output is mutation material, never evidence. Deterministic gates decide whether a candidate deserves simulation. Blinded observations decide whether a surviving model deserves scientific attention.

## NOVEL PROPOSAL: scientific fuzzing

Use high-temperature language-model sampling to generate many structured, nearly plausible physical models. Compile each model into a restricted JSON expression tree. Search for failures before searching for fit.

```text
Qwen mutator -> schema parser -> units/symmetry gate -> boundary/counterexample gate
             -> cheap simulation -> injection recovery -> cross-survey holdout
             -> full Bayesian comparison only for survivors
```

Every rejected candidate adds its failure signature to a deduplication archive. Future candidates with the same structural defect die before symbolic evaluation.

## Fitness

$$
F = 3I + 2N + 2D + R - 3C - 4V - 6H
$$

- $I$: expected information gain of cheapest next observation.
- $N$: structural novelty relative to archive.
- $D$: discriminability from named rival explanations.
- $R$: reproducibility from public data.
- $C$: compute/data cost.
- $V$: number and severity of violated deterministic constraints.
- $H$: hidden tuning, undefined quantities, or post-hoc choices.

Fitness may prioritize search. It cannot turn a failed gate into a pass.

## Cascaded cost funnel

| Gate | Typical cost | Purpose |
|---|---:|---|
| JSON/schema/tree-depth | microseconds | Reject malformed output and code injection |
| Dimensions/domain/boundary | milliseconds | Reject algebraic and physical type errors |
| SymPy + optional Wolfram counterexample | milliseconds-seconds | Simplify identities; find domain counterexamples |
| NSIDE 32-64 toy sky | seconds | Reject invisible or degenerate signatures |
| Injection recovery | minutes | Measure sensitivity and false positives |
| WMAP x Planck split | minutes-hours | Reject instrument-specific artifacts |
| Frequency/polarization veto | hours | Reject foreground and post-hoc fits |
| Calibrated Bayesian comparison | survivor only | Correct trials and compare against Lambda-CDM |

## Quality-diversity archive

Do not keep one globally highest-scoring theory. Keep one elite per niche:

- domain: CMB / quantum foundations / gravitational waves / topology / analogue gravity;
- observable cost band;
- mathematical mechanism;
- expected angular/frequency scale;
- dominant falsifier.

This prevents one fashionable family from consuming the whole search budget.

## Multifidelity acceleration

1. Generate $10^4$ structured candidates.
2. Reject malformed and dimensionally inconsistent candidates locally.
3. Simulate survivors at low resolution with fixed seeds.
4. Use active learning to refine only parameter regions with high expected information gain.
5. Train surrogates only after held-out coverage tests; neural posterior output without SBC/TARP coverage is invalid.
6. Preserve exact high-fidelity simulations as audit anchors.

## Cross-CAS policy

- `symbolically_screened`: SymPy passes all declared assumptions and sampled boundary checks.
- `wolfram_verified`: independent Wolfram Language evaluation agrees under identical assumptions.
- `cas_disagreement`: quarantine; never average or vote away disagreement.
- `empirically_supported`: reserved for blinded observational comparison; CAS cannot grant this status.

## Highest-leverage unconventional discriminator

For any temperature-disk candidate, freeze its polarization prediction before reading local $Q/U$ data. Then test phase coherence between radial temperature gradient and $E$-mode polarization while requiring no model-predicted primordial $B$-mode. This uses information not consumed during candidate generation and is harder for noise or foregrounds to imitate than temperature alone.

## Sources

- Romera-Paredes et al., *Nature* 2024, LLM-guided program search: https://doi.org/10.1038/s41586-023-06924-6
- Mouret & Clune 2015, MAP-Elites: https://arxiv.org/abs/1504.04909
- Wang et al. 2022, self-consistency: https://arxiv.org/abs/2203.11171
- McEwen et al. 2012, spherical optimal filters: https://arxiv.org/abs/1206.5035
- Feeney et al. 2011, WMAP bubble-collision search: https://arxiv.org/abs/1012.3667
- Wolfram AgentTools: https://github.com/WolframResearch/AgentTools
