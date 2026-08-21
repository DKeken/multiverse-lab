# Official Wolfram no-go verification

Use only official `mcp__wolfram_wolframlanguageevaluator`. Wolfram verifies submitted mathematics; it does not verify physical assumptions, quantum states, stability, or existence.

## Restricted renderer

Candidate identifiers are never interpolated. Compiler maps symbols to `Hyp$` plus UTF-8 hex and renders only `Plus`, `Times`, `Power`, `Exp`, `Log`, `Equal`, `And`, `Element`, `Greater`, `GreaterEqual`, `Less`, `LessEqual`, `FullSimplify`, `Refine`, `Limit`, and `Integrate` over compiler-owned expressions.

## Gate sequence

1. Recompute local candidate hash and schema hash.
2. Submit exact normalized assumptions used by SymPy.
3. Throat: `FullSimplify[shape[r0] == r0, assumptions]`.
4. Flare-out: `FullSimplify[D[shape[r], r] /. r -> r0 < 1, assumptions]`.
5. Horizon: `FullSimplify[Element[redshift[r], Reals], assumptions && r >= r0]`; unresolved is not pass.
6. Curvature: calculate declared invariant and `Limit[..., r -> r0, Direction -> "FromAbove"]`; indeterminate/divergent is reject.
7. NEC/ANEC: compare Wolfram-normalized contraction/integral with locally derived expression under identical conventions.
8. CAS disagreement emits terminal `cas_disagreement`; never vote, alter assumptions, or average results.

## Provenance required

Record tool name, official endpoint, request body hash, response hash, UTC timestamp, assumptions, compiler/schema hashes, and exact result. Only exact `True`/`False` or normalized symbolic equality may drive a deterministic gate; timeouts and conditional expressions remain `locally_screened`.
