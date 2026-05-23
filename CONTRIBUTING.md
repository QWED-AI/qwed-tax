# Contributing to QWED-Tax

Thank you for your interest in contributing to `qwed-tax`! We are building the world's most robust deterministic tax verification engine, and we need your help to cover the infinite edge cases of global tax law.

## ⚖️ The "Determinism" Rule
**Crucial:** QWED-Tax is NOT an estimator. It is a **Verifier**.
- We do not "guess" taxes.
- We implement the **Law**, not statistical likelihoods.
- Every check must return a binary `True` (Allowed) or `False` (Blocked), with exact reasoning.

## 🔐 Security Contract for Tests & Docs (Fail-Closed)
Tests and documentation are part of the verifier boundary contract.

- Missing, ambiguous, unknown, or unsupported inputs **must fail closed**.
- Tests must not normalize silent pass behavior (e.g., empty preflight payloads returning allowed).
- Documentation/examples must not imply "best effort" or skipped checks are acceptable verification.
- A claim should be described as verified only when:
  1) a supported `action` is provided, and
  2) at least one deterministic check actually executes.

If a behavior is insecure, tests/docs must describe it as a bug to fix, not intended behavior.

### PR checklist add-on (required)
For changes touching verifier boundaries, ensure PR includes:
- [ ] fail-closed tests for missing/invalid/unsupported inputs
- [ ] explicit expected-vs-actual verification reasoning in test names or docstrings
- [ ] documentation updates matching actual enforced behavior
- [ ] no language that overstates assurance beyond executed checks

## Development Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/QWED-AI/qwed-tax.git
   cd qwed-tax
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Run Tests:**
   ```bash
   pytest
   ```

## 📝 How to Add a New Tax Guard

1. **Choose a Jurisdiction:** Create a file in `qwed_tax/jurisdictions/<country>/`.
2. **Implement the Logic:** Use `decimal` for money and strictly typed rules.
   ```python
   # Example: Simple Flat Tax
   def verify_tax(amount: Decimal, tax: Decimal) -> VerificationResult:
       expected = amount * Decimal("0.10")
       if abs(tax - expected) > Decimal("0.01"):
           return VerificationResult(valid=False, message="Tax mismatch")
       return VerificationResult(valid=True)
   ```
3. **Add Tests:** Every guard MUST have a corresponding test case in `tests/`.

## 🐛 Reporting Bugs
Please open an issue describing:
- The Tax Law / Section involved.
- The input data.
- The expected behavior vs actual behavior.

## 📄 License
By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
