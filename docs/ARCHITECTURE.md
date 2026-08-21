# Architecture

## Design rule

Every expensive or epistemically strong action must consume a frozen, hashed artifact from a cheaper gate. No component may promote its own output beyond its authority.

## Code boundaries

| Module | Owns | Must not own |
|---|---|---|
| `hypothesis_compiler.py` | strict JSON, schema limits, canonical hash, safe AST | symbolic truth, observations |
| `local_verifier.py` | SymPy constructors, exact dimensions, conservative domains, Wolfram rendering | arbitrary parsing, empirical status |
| `wolfram_verifier.py` | exact request binding, response/provenance hashes, CAS status | request invention, physical evidence |
| `hypothesis_archive.py` | append-only events, status transitions, hash chain, niches | evaluation execution |
| `evaluation_scheduler.py` | prerequisite/cost/concurrency planning | running jobs, overriding hard fails |
| `cmb_fixture_repro.py` | controlled COMB/S2FIL fixture sensitivity | publication significance |
| `wmap_pilot.py` | masked global-null WMAP engineering diagnostic | multiverse inference, Planck unblinding |

## Canonical state

- Gate definitions: `research/operating-system.yml`
- Candidate schema: `research/hypothesis.schema.json`
- Event contract: `research/archive-contract.yml`
- Claim register: `research/claims.yml`
- Evidence ledger: `research/evidence-ledger.csv`
- Dataset identity: `data/registry.json`
- Experiment/provenance schemas: `research/*.schema.json`

Files are intentional for this alpha: no database, backend, scheduler service, or competing state store. Move to a package/CLI only after external contributors need stable imports.

## Status authority

```text
generated
  ├─ rejected
  └─ schema_valid
       ├─ rejected
       └─ locally_screened
            ├─ rejected
            ├─ cas_disagreement [terminal quarantine]
            └─ wolfram_verified
                 ├─ rejected
                 └─ simulation_eligible
                      ├─ rejected
                      └─ empirically_supported [observation gate only]
```

`empirically_supported` requires dataset SHA-256, preregistration/freeze hash, result hash, global multiplicity treatment, and human approval. It never means “proven true.”

## Security model

Untrusted LLM JSON is data. Duplicate keys, non-finite numbers, undeclared symbols, oversized trees, extra fields, inconsistent hashes, ambiguous domains, generated code, and altered Wolfram requests fail closed. Candidate identifiers are hex-encoded into safe Wolfram symbols.

## Compute model

- Local CPython orchestrates mature compiled engines.
- HEALPix transforms execute in healpy/ducc0; do not rewrite them without profiling evidence.
- Remote LLM is stateless mutation only, max one request in flight.
- Wolfram is independent mathematical verification only.
- Large observational holdouts require explicit approval.

## Planned package cutover

After two external integrations freeze the API:

```text
src/multiverse_lab/
  ir/          schema, compiler, dimensions
  evidence/    archive, provenance, claims
  scheduling/  multifidelity planner
  cosmology/   templates, masks, nulls, holdouts
  gravity/     restricted metrics and no-go checks
  cli.py
```

Until then, flat modules minimize migration and abstraction cost.
