from .models import Address, State

class AddressGuard:
    """
    Verifies physical address existence and consistency.
    (Stub implementation - in production would call USPS API or similar)
    """
    
    def verify_address(self, address: Address):
        """
        Checks if Zip Code matches State (Simplified heuristic).
        """
        zip_prefix = address.zip_code[:2]
        state = address.state
        
        # Simplified Zip Table
        valid_prefixes = {
            State.NY: ["10", "11", "12", "13", "14"],
            State.NJ: ["07", "08"],
            State.PA: ["15", "16", "17", "18", "19"],
            State.CA: ["90", "91", "92", "93", "94", "95", "96"],
            State.TX: ["75", "76", "77", "78", "79"],
            State.FL: ["32", "33", "34"]
        }
        
        if state not in valid_prefixes:
            return {"verified": True, "message": "State not in validation database yet (Assumed Valid)"}
            
        if zip_prefix in valid_prefixes[state]:
            return {"verified": True, "message": "✅ Zip code matches State."}
        else:
            return {
                "verified": False, 
                "message": f"❌ MISMATCH: Zip {address.zip_code} does not belong to {state.value}."
            }
