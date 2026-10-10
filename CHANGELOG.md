# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2026-10-10

Security patch release. Upgrading is recommended for all users of `NexusGuard` (Python and npm) and `ClassificationGuard`. A security advisory will be published alongside this release.

### Security
- **NexusGuard: structured claim required (#57, #62).** `check_nexus_liability` no longer interprets the free-text `llm_decision`. A verified result requires `claimed_collects_tax` as a boolean and is compared against the computed nexus liability. Without it, the result is `computed_only` (not verified). Negative or non-finite sales and transaction counts fail closed. `TaxPreFlight` action `economic_nexus` now requires `claimed_collects_tax`.
- **npm `NexusGuard` / `TaxPreFlight` (#63, #65).** The npm SDK enforces the same boolean `claimed_collects_tax` claim, fails closed on states that are not in its threshold table, and validates sales data (non-object, non-finite and negative values fail closed). The transaction-count prong only applies to states that have one.
- **ClassificationGuard: closed claim vocabulary and strict facts.** The worker-classification claim is mapped through a fixed set of values instead of substring matching: `W2` / `W-2` / `EMPLOYEE`, and `1099` / `1099-NEC` / `CONTRACTOR` / `INDEPENDENT CONTRACTOR` (any case; spaces, hyphens and underscores ignored). Any other text fails closed with `INVALID_CLAIM`. `provides_tools`, `reimburses_expenses` and `indefinite_relationship` must all be present booleans; otherwise the result fails closed with `INVALID_FACTS`. This applies to the Python `verify_classification_claim` and `TaxPreFlight` action `hire`. The npm SDK is unchanged and still compares `worker_type` exactly (`"W2"` / `"1099"`).

### Behaviour change
- Nexus callers that relied on `llm_decision` strings must pass `claimed_collects_tax: bool`.
- Classification claims outside the values above (for example `"1099 contractor"` or `"non-employee"`) are now rejected instead of being interpreted. Pass the canonical value (`"W2"` or `"1099"`). Worker facts must be real booleans, not strings such as `"no"`.

### CI
- The npm SDK test suite now runs on every push and pull request, alongside pytest (#80).

### Tests
- Regression tests for the nexus structured claim (Python and npm) and for the classification claim vocabulary and fact typing. Python suite: 312 passed; npm suite: 25 passed.

## [0.2.0] - 2026-06-22
### Added
- **TaxDiagnosticResult** — 3-layer structured diagnostic model (agent message / developer fields / proof ref) with tri-state status (VERIFIED / UNVERIFIABLE / BLOCKED). Closes #39.
- **`to_diagnostic()` on all 12 guards** — every guard now converts its legacy dict return into a `TaxDiagnosticResult` with cryptographic `proof_ref`. Closes #47.
- **Audit trace** — `build_trace()` + `RuleRef` entries for all 12 guards, covering IRS, CBDT, CBIC, FEMA, and OECD statutory references.
- **15 new RuleRef constants** in `audit.py` — CG (112A, 111A, 50AA), Speculation (43(5), 73), Inter-head (71, 74), VDA (115BBH), PoEM (6(3), CBDT 6/2017), FEMA (LRS, Schedule I, 206CR), IRS (Common Law, Pub 505), SAFE conversion.
- **`trace_proof_ref()`** — deterministic SHA-256 hash over audit trace, binds VERIFIED verdicts to specific evidence.
- **`TaxAdvisoryCheck`** — non-proof-bearing advisory metadata model with `advisory_only=True` invariant.

### Fixed
- **#16** — Fail-closed on unknown/unmodeled tax rules across all guards. Unknown services, states, asset types, and source strings now return `verified=False` instead of silently passing.
- **#17, #18** — Classification guard fail-closed on ambiguous facts + claim comparison. Mixed employee/contractor indicators no longer default to contractor.
- **#19, #40** — Middleware success label narrowed + ReciprocityGuard Z3 removed. `ARITHMETIC_VERIFIED` is a pre-conformance status, not a verification pass. Z3 solver replaced with deterministic lookup.
- **#20, #21, #22** — Input strictness: exact paise comparison (no tolerance), edge-case validation (negative amounts, zero values, discount=1), `extra="forbid"` on all 8 Pydantic input models.
- **#34, #31** — README repositioned as verification layer, not tax platform. "Production Ready" claims removed, non-goals section added, comparison table promoted to top.

### Changed
- **CryptoTaxGuard** — `TaxResult` pydantic model now includes optional `audit_trace` field.
- **PoEMGuard** — `_unverifiable()` helper now emits `audit_trace` with `INPUT_VALIDATION_FAILED` outcome.
- **`TaxDiagnosticResult.__post_init__`** — hardened with `isinstance` type checks for `status`, `agent_message`, and `developer_fields`.
- **`TaxDiagnosticResult.from_dict`** — validates `status` type (str → enum) and `developer_fields` type before construction.
- **`to_diagnostic()` fail-closed** — all 12 guards raise `ValueError` when `verified=True` but `audit_trace is None`.
- **BLOCKED vs UNVERIFIABLE** — `to_diagnostic()` now differentiates based on `audit_trace["outcome"]`: insufficient evidence/unknown rule → UNVERIFIABLE, claim wrong/invalid input → BLOCKED.

### Tests
- 270 tests (up from 83 in v0.1.0).
- 50 new tests for `to_diagnostic()` conversions covering VERIFIED, BLOCKED, UNVERIFIABLE, fail-closed, and serialization round-trip paths.
- 32 tests for `TaxDiagnosticResult` model, factory methods, `TaxAdvisoryCheck`, and `from_dict`/`to_dict`.

## [0.1.0] - 2026-01-30
### Added
- Initial release of `qwed-tax` verification engine.
- **US Jurisdiction:** PayrollGuard (FICA), ClassificationGuard (1099 vs W2).
- **India Jurisdiction:** CryptoTaxGuard (Sec 115BBH), RemittanceGuard (LRS).
- `examples/` directory with demo scripts.
- GitHub Marketplace integration support.
