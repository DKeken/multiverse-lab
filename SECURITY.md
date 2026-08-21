# Security policy

Report vulnerabilities privately through GitHub Security Advisories. Do not include secrets, private datasets, or exploit payloads in public issues.

## In scope

- Candidate JSON causing code execution, unsafe parser behavior, resource exhaustion, hash/provenance bypass, status escalation, archive corruption, or Wolfram injection.
- Dataset fetcher path traversal, hash bypass, or supply-chain substitution.
- Credential leakage from launchers, workflows, logs, manifests, or examples.

## Hard boundaries

Candidate content is untrusted data. `eval`, `exec`, arbitrary SymPy parsing, generated code execution, dynamic Wolfram heads, and automatic empirical promotion are forbidden. Dataset fetches require pinned hashes or Git revisions. Remote inference credentials and hosts belong in environment variables and never in Git.

Supported branch: `main`. Security fixes receive priority; no guaranteed response SLA is offered.
