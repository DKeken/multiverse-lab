# Portal feasibility: constraint-first program

## Decision

Portal engineering is not currently assessable because neither a physically accessible second universe nor a controllable causal relation to one has been established. Wormhole work below is a separate theoretical sandbox: it asks which geometries are internally consistent and what they would require. It cannot supply the missing destination evidence, prove multiverse existence, or establish buildability.

## Prerequisite evidence hierarchy

1. Observe a signature that discriminates a named multiverse model from conventional rivals.
2. Independently reproduce it across instruments and frozen holdouts.
3. Establish that the inferred region is causally accessible, not merely part of a cosmological model.
4. Define an operational destination variable.
5. Only then score channel creation and hardware feasibility.

Current work is at step 1. CMB bubble-collision searches constrain one model subclass; a null or candidate does not prove or disprove all multiverse theories.

## Machine-checkable static spherical baseline

For the Morris–Thorne family,

\[
ds^2=-e^{2\Phi(r)}dt^2+\frac{dr^2}{1-b(r)/r}+r^2d\Omega^2.
\]

| Check | Frozen condition | Meaning of failure | Scope/source |
|---|---|---|---|
| Throat | $b(r_0)=r_0$ | no throat at declared radius | Morris & Thorne 1988, https://doi.org/10.1119/1.15620 |
| Flare-out | $b'(r_0)<1$ | static throat pinches/fails this family | Morris & Thorne 1988 |
| Finite redshift | $\Phi(r)$ finite on path | horizon/non-traversability in this ansatz | Morris & Thorne 1988 |
| Curvature | finite declared invariants | singular candidate | direct differential-geometry check |
| NEC | $T_{\mu\nu}k^\mu k^\nu$ at throat | identifies exotic stress-energy requirement; not a universal theorem for every modified-gravity model | Morris & Thorne 1988 |
| ANEC/topology | integral along complete null geodesic under theorem assumptions | conflicts with topological-censorship assumptions | Friedman, Schleich & Witt 1993, https://doi.org/10.1103/PhysRevLett.71.1486 |
| QEI | sampled negative energy above field/state-specific lower bound | proposed source violates applicable semiclassical bound | Ford & Roman 1996, https://doi.org/10.1103/PhysRevD.53.1988 |
| Tidal | $|R_{\hat0\hat j\hat0\hat k}\xi^k|\le a_{max}$ | payload unsafe under declared limit | Morris & Thorne 1988 |
| Stability | bounded linear perturbation spectrum | no demonstrated stable operating point | model-specific numerical check |
| Backreaction | semiclassical correction small relative to background | fixed-background approximation invalid | model-specific; unknown until quantum state specified |
| Chronology | no closed timelike curve from mouth motion/offset | chronology hazard; general protection remains conjectural | Hawking 1992, https://doi.org/10.1103/PhysRevD.46.603 |
| Targeting | operational boundary conditions identify both mouths | geometry is not a navigation mechanism | no established inter-universe coordinate protocol |

## Important boundaries

- Topological censorship and energy-condition results have assumptions. They are constraints, not an assumption-free proof that every conceivable portal is impossible.
- Gao–Jafferis–Wall traversability uses a special AdS/CFT construction and boundary coupling; it is not a flat-spacetime engineering recipe: https://arxiv.org/abs/1608.05687.
- Quantum teleportation transfers a quantum state using entanglement plus classical communication; it does not transport matter or open spacetime.
- Analogue gravity and holographic simulations test equations/analogies. They do not create a macroscopic gravitational throat.

## Fastest search loop

1. Compile only `portal-feasibility.schema.json`; reject arbitrary tensors/code.
2. Derive $G_{\mu\nu}$ locally with SymPy for the restricted family.
3. Recheck frozen identities with official Wolfram MCP.
4. Reject horizon, singularity, throat, flare-out, dimension, or domain failures before integration.
5. Compute NEC/ANEC and tidal ledger; label QEI/backreaction `unknown` until a field and quantum state are declared.
6. Numerically perturb only survivors.
7. Never promote beyond `simulation_eligible` without an observation manifest.
