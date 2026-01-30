# 🗺️ QWED-Tax Roadmap

This document outlines the strategic direction for `qwed-tax`, the deterministic tax verification engine. Our goal is to cover 80% of global GDP tax jurisdictions by 2026 with mathematical certainty.

## 🚀 Phase 1: Foundation (Current Status: ✅ Live)
- **Jurisdictions:** US (IRS), India (CBDT/GST).
- **Core Guards:**
    - `PayrollGuard` (US FICA, India TDS).
    - `CryptoTaxGuard` (India Sec 115BBH).
    - `RemittanceGuard` (FEMA LRS Limits).
    - `GSTGuard` (RCM logic).
- **Delivery:** Python SDK, GitHub Action (v1).

---

## 🏗️ Phase 2: Global Expansion (Q2 2026)
Expanding coverage to major English-speaking jurisdictions.

### 🇬🇧 United Kingdom (HMRC)
- [ ] **VATGuard:** Verify 20% Standard vs 5% Reduced vs 0% Zero-rated categories.
- [ ] **PAYEGuard:** Verify Pay As You Earn calculations against tax codes (1257L).
- [ ] **IR35Guard:** Deterministic checks for "Inside vs Outside" IR35 status for contractors.

### 🇨🇦 Canada (CRA)
- [ ] **GSTHSTGuard:** Verify complex Provincial (PST) vs Federal (GST) vs Harmonized (HST) rules per province.
- [ ] **RRSPGuard:** Verify contribution room and over-contribution penalties.

### 🇦🇺 Australia (ATO)
- [ ] **SuperGuard:** Verify Superannuation Guarantee (SG) contributions (11.5% rate checks).
- [ ] **GSTGuard:** 10% GST logic with exemptions for fresh food/medical.

---

## 🧠 Phase 3: Deep Logic & Transfer Pricing (Q3 2026)
Moving beyond simple rates to complex inter-company logic.

### 🌐 Transfer Pricing (Arm's Length Principle)
- [ ] **ALPGuard:** Verify inter-company transaction pricing against comparable uncontrolled prices (CUP).
- [ ] **BEPSGuard:** Base Erosion and Profit Shifting checks (OECD Pillar 2).

### 📉 Advanced Deductions
- [ ] **DeductionGuard (US):** Section 179 depreciation deterministic logic.
- [ ] **ExemptionGuard (India):** HRA (House Rent Allowance) exemptions based on Metro/Non-Metro rules (min(Rent-10%, 50% Basic, Actual)).

---

## 🏢 Phase 4: Enterprise Integrations (Q4 2026)
Seamless connection with financial systems.

- [ ] **ERP Connectors:**
    - SAP S/4HANA Adapter.
    - Oracle NetSuite Plugin.
    - QuickBooks / Xero Webhooks.
- [ ] **LMS (Legal Management System) Integration:**
    - Sync with `qwed-legal` to verify contract terms match invoice tax treatment.

## 🔮 Long Term Vision
- **Automated Filing:** Generate filled-in PDF tax forms (1040, ITR-V) post-verification.
- **Real-Time Audit:** Continuous verification of every ledger entry as it happens.
