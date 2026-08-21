# Contributing

## Best first contributions

- Reproduce a frozen result on another platform.
- Add null simulations, injection coverage, foreground/systematics vetoes, or independent dataset adapters.
- Supply a counterexample to a symbolic gate.
- Implement one roadmap invention behind an existing contract.
- Improve source provenance or correct an overstated claim.

## Required hypothesis shape

Every proposal must name:

1. Epistemic class: `ESTABLISHED`, `ADAPTED`, `NOVEL PROPOSAL`, or `UNVERIFIED`.
2. Primary sources and exact assumptions.
3. Observable and decision rule.
4. At least one conventional rival explanation.
5. Falsifier and cheapest decisive test.
6. Units/domains and expected compute/data cost.
7. Trial factors, nuisance parameters, and holdout boundary.
8. Conclusions the result cannot support.

Use the Hypothesis issue form. Unsupported free-form extraordinary claims may be closed without implementation work.

## Development

```bash
uv sync --frozen
make check
```

Data and upstream source fixtures are fetched, never committed:

```bash
bun scripts/fetch-data.ts --group fixture
```

## Pull requests

- One scientific or code contract per PR.
- Add observable behavioral coverage for code changes.
- Do not weaken fail-closed gates to make a candidate pass.
- Update evidence/claims ledgers when epistemic meaning changes.
- Record datasets by URL, hash, release, license, role, and redistribution status.
- Do not open declared holdouts or add files over 10 MiB without maintainer approval.
- Generated code execution, private data, credentials, and undisclosed paid services are prohibited.

## Review criteria

Correctness and scientific authority first; maintainability second; novelty third. A negative result or rejected hypothesis is a successful contribution when reproducible.
