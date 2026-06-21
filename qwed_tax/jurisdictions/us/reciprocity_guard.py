from typing import Optional

from ...models import WorkArrangement, State

class ReciprocityGuard:
    """
    Verifies State Income Tax Reciprocity Agreements.
    Example: NJ residents working in PA do NOT pay PA tax, they pay NJ tax.
    """

    def __init__(self):
        self.reciprocal_pairs = {
            (State.NJ, State.PA), (State.PA, State.NJ),
            (State.MD, State.PA), (State.PA, State.MD),
            (State.VA, State.MD), (State.MD, State.VA),
        }

    def determine_withholding_state(self, arrangement: WorkArrangement) -> dict:
        """
        Determines the correct withholding state for a work arrangement.
        Returns verified=True only when the withholding state can be
        deterministically proven (same state or known reciprocity pair).
        Returns verified=False when no reciprocity exists — the guard
        cannot verify withholding treatment without a claim to compare.
        """
        residence = arrangement.residence_address.state
        work = arrangement.work_address.state
        return self._evaluate_reciprocity(residence, work)

    def verify_reciprocity(
        self,
        residence_state: str,
        work_state: str,
        same_state: Optional[bool] = None,
    ) -> dict:
        """
        Verifies whether a state tax reciprocity agreement exists between
        the residence and work states.

        Returns verified=True only when:
        - Both states are the same (no reciprocity needed), or
        - A known reciprocity agreement exists between the states

        Returns verified=False when:
        - The states are different and no reciprocity agreement exists
        - Either state is not recognized
        - same_state claim conflicts with actual state values
        """
        residence = self._coerce_state(residence_state)
        if residence is None:
            return {
                "verified": False,
                "message": f"Unknown residence state '{residence_state}'. Cannot verify reciprocity.",
            }

        work = self._coerce_state(work_state)
        if work is None:
            return {
                "verified": False,
                "message": f"Unknown work state '{work_state}'. Cannot verify reciprocity.",
            }

        if same_state is not None and same_state != (residence == work):
            return {
                "verified": False,
                "message": (
                    "same_state claim conflicts with residence/work states. "
                    "Cannot verify reciprocity."
                ),
            }

        return self._evaluate_reciprocity(residence, work)

    def _evaluate_reciprocity(self, residence: State, work: State) -> dict:
        if residence == work:
            return {
                "verified": True,
                "withholding_state": residence,
                "reason": "Employees living and working in same state pay that state tax.",
            }

        if (residence, work) in self.reciprocal_pairs:
            return {
                "verified": True,
                "withholding_state": residence,
                "reason": (
                    f"Reciprocity Agreement exists between {residence.value} and "
                    f"{work.value}. Withhold for Residence ({residence.value})."
                ),
            }

        return {
            "verified": False,
            "withholding_state": work,
            "reason": (
                f"No reciprocity agreement between {residence.value} and {work.value}. "
                f"Default withholding is for Work State ({work.value}), but the guard "
                f"cannot verify the claimed withholding treatment without a claim to compare."
            ),
        }

    @staticmethod
    def _coerce_state(value) -> State | None:
        if isinstance(value, State):
            return value
        if isinstance(value, str):
            try:
                return State(value.strip().upper())
            except ValueError:
                return None
        return None
