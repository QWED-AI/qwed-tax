<div align="center">

# 💸 QWED-Tax
**Deterministic Verification for Payroll & Tax Compliance**

> "Death, Taxes, and Deterministic Verification."

[![Verified by QWED](https://img.shields.io/badge/Verified_by-QWED-00C853?style=flat&logo=checkmarx)](https://github.com/QWED-AI/qwed-tax)
[![PyPI](https://img.shields.io/pypi/v/qwed-tax?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/qwed-tax/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

</div>

---

## 🚨 The Problem
AI agents are handling payroll. **LLMs are notoriously bad at math.**
*   `$0.1 + $0.2` often equals `$0.3000000004` (Floating Point Error).
*   Miscalculating withholdings leads to IRS fines (approx $280 per misclassified employee).

## 💡 What QWED-Tax Is
A deterministic verification layer for tax logic.
*   **Engine:** `python-decimal` for exact currency math.
*   **Logic:** `z3-solver` for W-2 vs 1099 classification rules.
*   **Data:** 2025/2026 Tax Brackets (Embedded).

## 🛡️ The Guards
1.  **PayrollGuard**: Verifies Gross-to-Net calculations (Fed/State/FICA).
2.  **WithholdingGuard**: Verifies W-4 claims against IRS Pub 15-T.
3.  **ClassificationGuard**: Prevents 1099 misclassification using Common Law rules.

## 📦 Installation
```bash
pip install qwed-tax
```
