from decimal import Decimal
from qwed_tax.jurisdictions.india import (
    CryptoTaxGuard, AssetClass,
    InvestmentGuard, TransactionType,
    GSTGuard, EntityType, ServiceType
)

def run_audit_checks():
    print("📋 QWED Tax Audit Verification (India Jurisdiction)")

    # --- 1. Crypto Loss Set-Off (Section 115BBH) ---
    print("\n--- ₿ Testing Crypto Loss Set-Off ---")
    cg = CryptoTaxGuard()
    
    # Scenario: User has 50k Business Gain, 20k Crypto Loss.
    # LLM tries to pay tax on (50k - 20k) = 30k.
    # QWED should BLOCK this.
    losses = {"VDA": Decimal("-20000")}
    gains = {"BUSINESS": Decimal("50000")}
    
    res_crypto = cg.verify_set_off(losses, gains)
    print(f"Result: {res_crypto.message}")
    print(f"Verified? {res_crypto.verified}")

    # --- 2. Intraday vs Delivery Check ---
    print("\n--- 📈 Testing Intraday Classification ---")
    ig = InvestmentGuard()
    
    # Scenario: Intraday Trade (Speculative)
    res_intra = ig.verify_classification(TransactionType.INTRADAY, holding_period_days=0)
    print(f"Intraday Trade: {res_intra['classification']} -> {res_intra['tax_treatment']}")
    
    # Scenario: Delivery > 1 Year (LTCG)
    res_ltcg = ig.verify_classification(TransactionType.DELIVERY, holding_period_days=400)
    print(f"Long Term Hold: {res_ltcg['classification']} -> {res_ltcg['tax_treatment']}")

    # --- 3. GST Reverse Charge (RCM) ---
    print("\n--- 🚚 Testing GST RCM (GTA) ---")
    gst = GSTGuard()
    
    # Scenario: GTA Service -> Company
    res_rcm = gst.verify_rcm_applicability(ServiceType.GTA, EntityType.INDIVIDUAL, EntityType.BODY_CORPORATE)
    print(f"GTA to Company: Liability on {res_rcm['liability']}")
    
    # Scenario: GTA Service -> Individual (Unregistered) - Not handled in simplified logic but checking default
    # Scenario: Legal Service -> Company
    res_legal = gst.verify_rcm_applicability(ServiceType.LEGAL, EntityType.PARTNERSHIP, EntityType.BODY_CORPORATE)
    print(f"Legal to Company: Liability on {res_legal['liability']}")

if __name__ == "__main__":
    run_audit_checks()
