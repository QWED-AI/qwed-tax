<div align="center">

# 💸 QWED-Tax
**Deterministic Verification for Payroll, Tax, and Compliance**

> "Death, Taxes, and Deterministic Verification."

[![Verified by QWED](https://img.shields.io/badge/Verified_by-QWED-00C853?style=flat&logo=checkmarx)](https://github.com/QWED-AI/qwed-tax)
[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Pending_Publish-orange?logo=github)](https://github.com/marketplace/qwed-security)
[![PyPI](https://img.shields.io/pypi/v/qwed-tax?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/qwed-tax/)
[![NPM](https://img.shields.io/npm/v/@qwed-ai/tax?color=red&logo=npm&logoColor=white)](https://www.npmjs.com/package/@qwed-ai/tax)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

</div>

---

## 🚨 The Problem: AI Hallucinations in Tax
AI agents are handling payroll and tax, but **LLMs are largely illiterate in tax law.**

## 🏗️ Architecture: The "Swiss Cheese" Defense

```mermaid
graph TD
    A["🤖 AI Agent"] -->|"Intent"| B{"🛡️ QWED-Tax Pre-Flight"}
    
    subgraph "Deterministic Guards"
    C["Personal Tax<br/>(Payroll, 1099 vs W2)"]
    D["Trading Tax<br/>(F&O, Crypto, STCG)"]
    E["Corporate Tax<br/>(Sec 185 Loans, Valuations)"]
    end
    
    B --> C & D & E
    C & D & E -->|"Audit Result"| B
    
    B -- "✅ Verified" --> F["🚀 Fintech API (Avalara/Gusto)"]
    B -- "🛑 Blocked" --> G["🚫 Stop & Throw Error"]
    
    style B fill:#00C853,stroke:#333,stroke-width:2px,color:white
    style G fill:#ff4444,stroke:#333,stroke-width:2px,color:white
```

## 🔒 Zero-Data Leakage
Unlike cloud APIs check (Avalara/Vertex), `qwed-tax` runs **100% Locally**.
*   **Privacy First:** Your payroll/trading data never leaves your server.
*   **No API Latency:** Checks are instant (microseconds).
*   **GDPR/DPDP Compliant:** Ideal for sensitive Fintech environments.

> 📖 **See [Determinism Guarantee](https://docs.qwedai.com/docs/engines/overview#deterministic-first-philosophy)** for how QWED ensures 100% reproducible verification.

## 🌐 TypeScript SDK (New!)
Run compliance checks proactively in the browser/frontend.

```bash
npm install @qwed-ai/tax
```

```typescript
import { TaxPreFlight } from '@qwed-ai/tax';

const result = TaxPreFlight.audit({
  action: "hire",
  worker_type: "1099",
  worker_facts: { provides_tools: true, reimburses_expenses: true } // implies Employee
});

if (!result.allowed) {
   alert(" Compliance Block: " + result.blocks.join(", "));
}
```

### ⚔️ Why QWED-Tax?
Unlike calculators (Avalara) or executors (Gusto), QWED is a **Verifier**. We sit *between* the AI and the Execution.

| Solution | What They Do | The Risk | QWED's Role |
| :--- | :--- | :--- | :--- |
| **Avalara / Stripe** | **Calculate** tax based on inputs. | Garbage In, Garbage Out. If AI sends wrong input, tax is wrong. | **The Filter:** We verify inputs *before* API calls. |
| **Gusto / Check** | **Execute** payments and filings. | They execute erroneous commands (e.g., paying a W-2 as 1099). | **The Shield:** We block illegal payments *before* execution. |
| **Blue J / ChatGPT** | **Research** tax law. | Hallucination (85% accuracy). | **The Proof:** We verify the math & logic deterministically. |

### 📊 Real World Failures We Blocked (From Audit Logs)
| Scenario | LLM Hallucinations | QWED Verdict |
| :--- | :--- | :--- |
| **Senior Citizen FD** | "Base 7% + 0.5% = 7.50000001%" (Float Error) | 🛑 **BLOCKED** (Exact 7.50%) |
| **Loss Set-Off** | "Set off Intraday Loss against Salary" | 🛑 **BLOCKED** (Illegal Inter-head adjustment) |
| **Crypto Tax** | "Deduct Bitcoin loss from Business Profit" | 🛑 **BLOCKED** (Sec 115BBH violation) |
| **Payroll** | "FICA Tax on $500k = $31,000" | 🛑 **BLOCKED** (Limit is $176k / ~$10k tax) |

## 🧠 Procedural Accuracy (MSLR Aligned)
Unlike standard calculators, `qwed-tax` verifies the **procedure**, not just the result. This aligns with **Multi-Step Legal Reasoning (MSLR)** to prevent "Right Answer, Wrong Logic" errors.

*   **Step 1: Sanction Check** $\rightarrow$ Is this transaction legal? (e.g., `RelatedPartyGuard` blocks illegal loans *before* rate checks).
*   **Step 2: Limit Check** $\rightarrow$ Is it within quota? (e.g., `RemittanceGuard` checks LRS limit *before* TCS).
*   **Step 3: Calculation** $\rightarrow$ Apply math.

## 💡 What QWED Tax Verification System
![QWED Security](https://img.shields.io/badge/QWED-Secured-blueviolet)

> **Enterprise-Grade Tax Code Verification Engine**
A deterministic verification layer for tax logic supported by `z3-solver` and `python-decimal`. It supports multiple jurisdictions.

| Feature | US Jurisdiction (IRS) 🇺🇸 | India Jurisdiction (CBDT) 🇮🇳 |
| :--- | :--- | :--- |
| **Engine** | `z3` (ABC Test), `decimal` | `z3` (Intraday Rules), `decimal` |
| **Key Guards** | Payroll, FICA Limit, W-2/1099 | Sec 115BBH (Crypto), GST (RCM) |
| **Status** | ✅ Production Ready | ✅ Production Ready |

## 🛡️ The Guards

### 🇺🇸 United States (IRS)
1.  **PayrollGuard**: Verifies Gross-to-Net logic and enforces **2025 FICA Limit** ($176,100).
2.  **ClassificationGuard (IRS Common Law)**: Uses deterministic rules to verify W-2 vs 1099 status.
3.  **ReciprocityGuard**: Deterministically verifies state tax withholding (NY vs NJ rules).
4.  **NexusGuard**: Verifies **Economic Nexus** thresholds ($100k/$500k sales) to catch missing tax liabilities.

### 🇮🇳 India (Income Tax / GST / FEMA)
1.  **CryptoTaxGuard**: Enforces **Section 115BBH** (No set-off of VDA losses).
2.  **InvestmentGuard**: Distinguishes **Intraday (Speculative)** from **Delivery (Capital Gains)** using strict rules.
3.  **GSTGuard**: Verifies **Reverse Charge Mechanism (RCM)** for GTA/Legal services.
4.  **RemittanceGuard (FEMA)**:
    *   **LRS Limit**: Enforces $250,000 annual limit per PAN.
    *   **Prohibited**: Blocks Gambling, Lottery, and Racing remittances.
    *   **TCS**: Applies 20% Tax Collected at Source on generic investments/tours.
5.  **Accounts Payable Guards**:
    *   **InputCreditGuard**: Blocks ITC on 'Blocked List' (Sec 17(5)) like Food/Motor Vehicles.
    *   **TDSGuard**: Enforces withholding tax (1% vs 10%) on Contractor/Professional payments.

## 📦 Installation
```bash
pip install qwed-tax
```

## ⚡ Usage
```python
from qwed_tax.verifier import TaxVerifier

# 1. US FICA Check
us_tax = TaxVerifier(jurisdiction="US")
# ... usage (facade methods to be added or verified) ...

from qwed_tax.jurisdictions.us import PayrollGuard
pg = PayrollGuard()
result = pg.verify_fica_tax(gross_ytd=180000, current=5000, claimed_tax=310)
print(result.message) 
# -> "❌ FICA Error: Expected $68.20 (Hit Limit)"

# 2. India Crypto Check
in_tax = TaxVerifier(jurisdiction="INDIA")
res = in_tax.verify_india_crypto(losses={"VDA": -5000}, gains={"BUSINESS": 50000})
print(res.message) 
# -> "⚠️ Section 115BBH Alert: VDA loss cannot be set off."

## 🧾 Accounts Payable (AP) Automation
`qwed-tax` now secures the entire "Procure-to-Pay" cycle for AI Agents:
*   **Validation:** Checks GSTIN/VAT ID formats.
*   **Compliance:** Blocks Input Tax Credit (ITC) on "Personal" categories (Food, Cars, Gifts).
*   **Withholding:** Auto-calculates TDS/Retention amounts before commercial payment.
```

## ⚡ Usage (Frontend)
```python
from qwed_tax.verifier import TaxPreFlight

preflight = TaxPreFlight()
report = preflight.audit_transaction({
    "worker_type": "1099",
    "worker_facts": {"provides_tools": True, "reimburses_expenses": True}, # Employee traits
    "state": "NY", 
    "sales_data": {"amount": 600000} # Crosses Nexus
})

if not report["allowed"]:
    print(f"🛑 BLOCKED: {report['blocks']}")
```

## 📂 Examples
Check the `examples/` directory for runnable scripts:
- `examples/demo_payroll.py`: US FICA & Payroll verification.
- `examples/demo_advanced.py`: Complex Investment & Trading checks.

## 🗺️ Roadmap
We have a massive vision for Global Tax Verification.
Check out our **[Detailed Roadmap](ROADMAP.md)** for 2026 plans including:
- 🇬🇧 UK (HMRC) & 🇨🇦 Canada (CRA) Support
- Transfer Pricing & BEPS Guards
- ERP Integrations (SAP/Oracle)

## 📦 Related Packages

| Package | Description |
|---------|-------------|
| [qwed-verification](https://github.com/QWED-AI/qwed-verification) | Core verification engine |
| [qwed-finance](https://github.com/QWED-AI/qwed-finance) | Banking & derivatives verification |
| [qwed-mcp](https://github.com/QWED-AI/qwed-mcp) | Claude Desktop integration |

---

## 🤝 Contributing
We welcome contributions from Tax Experts and Developers!
See **[CONTRIBUTING.md](CONTRIBUTING.md)** for guidelines.

## 📄 License
Apache 2.0
