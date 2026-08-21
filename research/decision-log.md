# Decision log

## Supported now

- Exact COMB/healpy fixture geometry works: signal-only localization recovers all five source centers.
- Noisy fixture sensitivity is four of five under the frozen diagnostic false-peak budget.
- The 128-null WMAP/KQ75 diagnostic found no global threshold exceedance: empirical diagnostic p=0.1318.
- Restricted hypothesis JSON can be screened for integrity, dimensions, conservative domains, archive transitions, cost, and independent CAS agreement.
- Official Wolfram returned `True` for the compiler-owned identity; scope is mathematical only.
- The WMAP maximum is 1.103 degrees from the published Cold Spot reference and is treated as a rediscovery, not a new bubble candidate.
- Integer evidence gives an exact deterministic five-sigma null-budget minimum of 59,305,448; temperature-only expansion to one million nulls is futile for that target.
- Synthetic temperature selection over 256 trials inflated a naive nominal z>=3 E-mode confirmation to 13.684 percent versus a 0.135 percent Gaussian target; conditioning E on selected T restored calibration to 0.195 percent.
- CAMB 2.0.3 gives a frozen 5-degree filtered T/E correlation of 0.08195 with two TE sign changes; conditional calibration passes both template orientations while naive false-positive rates vary from 0.073 to 0.305 percent.
- Public CAMB 2.0.3 plus a repository-owned Feeney Eq. 1-4 adapter produces converged five-degree unit-linear and unit-quadratic T/E basis templates; reconstructed TT/EE/TE p95 relative errors are all below 0.078 percent.
- Cosmic-variance-only Fisher decomposition gives joint-over-temperature information ratios of 1.740 for the linear basis and 1.607 for the quadratic basis; the basis correlation is 0.964, so these are fixed-other-basis forecasts rather than marginalized observational sensitivities.
- Frozen synthetic `NSIDE=64`, `lmax=96` T/Q/U injection through a 20-degree Galactic cut and 5-degree C2 apodization retains 99.969 percent of conditional-E signal-to-noise; NaMaster recovers 4.99846 sigma from the expected 4.99846 sigma with 0.0000166 sigma B leakage.
- Exact 100 GHz PySM3 d1+s1 template deprojection changes the recovered score by 4.04e-16 sigma. This validates the projection operator only; foreground-model mismatch, beam, anisotropic noise, and calibration remain untested.
- The frozen mismatch stress fails overall: d2+s2 truth at 105 GHz versus d1+s1 nuisance templates at 100 GHz, 60 versus 55 arcmin beams, 1 percent gain error, 0.5-degree angle error, and 2-to-6 uK per-pixel anisotropic noise leave only 0.926 expected sigma and -0.739 realized sigma, below the frozen 3-sigma gate.
- Injection response itself remains stable at 0.392 percent bias; foreground residual is -0.045 sigma and B score -0.00428 sigma. The active blocker is noise depth in this fixed scenario, not foreground or beam-response bias.
- Analytic Gaussian power forecast requires base Q/U noise no larger than 0.192293 uK per pixel under the inherited one-to-three depth pattern, 10.4 times below the failed 2 uK per-pixel stress depth.
- Independent harmonic validation passes exactly at its preregistered boundary: 58 of 64 seeds exceed 3 sigma, with mean 4.260 sigma and sample standard deviation 0.903. Treat this as a fragile synthetic design requirement, not proof of 90 percent power or Planck sensitivity.
- Matrix-free cut-sky inverse filtering solves the 65024-dimensional anisotropic Q/U covariance without a dense matrix; six template/nuisance CG solves converge in 99 to 124 iterations with relative residual below 9.42e-8.
- The inherited 0.192293 uK per-pixel harmonic depth is rejected by the more exact operator: 55 of 64 seeds exceed 3 sigma rather than the frozen 58, mean E score is 3.990 sigma, and maximum absolute B diagnostic is 3.601 sigma versus the 3-sigma veto. Recalibration must be a new preregistered gate.
- Instrument feasibility stops the synthetic series: the frozen requirement equals map depth of roughly 10 uK-arcmin at NSIDE=64, while Planck HFI polarization is order 600 to 1000 uK-arcmin per channel (at least 30 times short even with an optimistic three-channel combination) and WMAP polarization is worse; CMB-S4-class 1 to 2 uK-arcmin gives 5 to 10 times margin. Planck Q/U stays closed as non-viable for this statistic at the frozen unit-basis 5-sigma amplitude. The requirement is conditional on that arbitrary amplitude; a physically motivated amplitude prior is the next scientific input, and the synthetic gate series stops here rather than recalibrating depth again.
- Physical amplitude mapping closes the five-degree conditional T/E program: the stored injection sat 1.94x above the fiducial linear maximum and 2.3e5x above the quadratic maximum; the quadratic basis has a 2e-5 sigma perfect-experiment ceiling, typical linear amplitudes give 0.02 to 0.20 sigma ceilings, and only the extreme Planckian-excursion corner reaches 3.99 sigma even with zero noise and full sky. No current or funded instrument is deeper than 5x short of the extreme-corner requirement. Future work must change geometry or observable and recompute the mapping; this is a forecast no-go, not an observational constraint.
- Geometry scan reverses the program outlook away from five degrees only: joint-linear sigma improves from 3.42e-4 to 4.32e-5 across 5 to 60 degrees while the fiducial physical maximum grows 131-fold, so ceilings rise from 3.99 to 4145 sigma and typical amplitudes reach 3.38 sigma at 10 degrees and 11.4 to 207 sigma at 15 to 60 degrees. Large-radius templates are low-ell dominated, where Planck and WMAP temperature maps are closest to cosmic variance, so a preregistered analytic-threshold temperature filter on development WMAP data is the next gate before any holdout question. Ceilings are lower bounds and not expectations; existing searches already exclude part of this space.

## Excluded conclusions

- WMAP result does not prove or disprove a multiverse.
- CMB bubble signatures would test one inflationary subclass, not Many-Worlds or every multiverse model.
- A CAS result or simulation cannot become empirical evidence.
- No accessible destination, causal channel, targeting protocol, macroscopic negative-energy source, stable throat, or portal hardware has been established.
- Portal engineering therefore remains `not-assessable`, not proven impossible and not supported.
- CAS-CI demand, pricing, and moat remain hypotheses until approved customer validation.

## Corrections made

- Replaced premature portal verdict `unsupported` with `not-assessable`; prerequisite target-existence and causal-access gates now come first.
- Separated S2FIL sharp demo template (`zc=-1`) from exact COMB fixture generator (`zc=0.2`, smooth tail).
- Separated fixture beam 13.2 arcmin from WMAP ILC 1 degree beam.
- Corrected CAMB spectrum conversion: fixture maps use mK² while WMAP pilot uses K².
- Replaced single-null observational interpretation with 128-null global diagnostic across positions, signs, and four scales.
- Preserved Planck temperature/frequency/polarization products as unopened holdouts requiring approval.
- Replaced the planned standalone radial Qr/Ur experiment because WMAP/Planck Cold Spot analyses already implemented it; the next gate is conditional joint T/E with nuisance projection and B veto.
- Restricted AIPOCH to optional provenance review; repository artifacts remain authoritative and AIPOCH cannot promote scientific evidence.
- Selected maintained CAMB plus a minimal spatial-profile adapter instead of adopting the Python-2-era CosmoBubbles runtime; CAMB owns transfer physics and the repository owns only the missing profile-to-transfer integration.
- Applied CAMB's exact spin-2 E normalization from `CalcScalCls` and verified it by independently reconstructing unlensed scalar TT/EE/TE.
- Pinned NaMaster 3.0.1 and PySM3 3.4.6 in the optional `masked-te` environment so native cut-sky engines do not burden portable core CI; OpenMP is disabled because it changes performance, not the estimator.
