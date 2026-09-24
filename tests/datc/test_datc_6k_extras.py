"""DATC section 6.K — the two cases the reference implementation added itself.

6.K is not part of the published DATC (which ends at 6.J); these are Paquette's
own additions in the legacy tree's `test_datc.py`, and they cover two behaviours
nothing else in this suite pins:

- **6.K.1** — civil disorder when a power disbands *some* of what it owes. The
  6.J cases all order either everything or nothing, so the "finish the job"
  branch of the distance rule was untested here until the pre-deletion audit of
  `old_implementation/` (Track W).
- **6.K.2** — a support of a *convoying fleet* stays valid even when the convoy
  it was part of fails. Easy to break while implementing the (correct) rule that
  support for a convoyed *army* is void when the convoy fails.

Both outcomes were verified against the legacy resolver before being asserted
here (`git show v2.7.68:old_implementation/diplomacy/tests/test_datc.py`); this
engine agrees with it on both, unit for unit.
"""

from __future__ import annotations

import pytest

from engine.types import PhaseType, ResultCode, Season
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6k1_civil_disorder_with_some_orders():
    """6.K.1. England owes two removals and orders one; the rule finishes the job.

    Seven units, five centres. England disbands F Gulf of Bothnia itself. Civil
    disorder must then remove exactly one more, and the distance rule picks
    F St Petersburg/NC — the farthest from a home centre — rather than
    re-removing the unit that is already gone.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("ENGLAND", "A RUH", "A HOL", "A EDI", "F NTH", "F BOT", "F STP/NC", "F IRI")
    h.owns("ENGLAND", "EDI", "LON", "HOL", "SWE", "STP")
    h.orders("ENGLAND", "F BOT D")
    h.adjudicate_adjustments()

    h.assert_disbanded("F BOT")
    h.assert_disbanded("F STP/NC")
    assert h.unit_count("ENGLAND") == 5, "England must end with exactly five units"
    for province in ("RUH", "HOL", "EDI", "NTH", "IRI"):
        assert h.final_at(province) == "ENGLAND", f"{province} should not have been removed"


def test_6k2_support_of_a_failed_convoying_fleet_still_holds():
    """6.K.2. The convoy fails, but the support of the convoying fleet does not.

    France convoys A Brest to Clyde via Mid-Atlantic and the Irish Sea — a route
    that does not exist (Clyde does not touch the Irish Sea), so the convoy is
    NO_CONVOY. England attacks Mid-Atlantic with support. The point of the case:
    F Western Mediterranean's support of F Mid-Atlantic is unaffected by the
    convoy's failure, so the attack bounces and nothing is dislodged.
    """
    h = Harness()
    h.units("FRANCE", "F MAO", "F IRI", "A BRE", "F WES")
    h.units("ENGLAND", "F NAO", "F ENG")
    h.orders(
        "FRANCE",
        "F MAO C A BRE - CLY",
        "F IRI C A BRE - CLY",
        "A BRE - CLY VIA",
        "F WES S F MAO",
    )
    h.orders("ENGLAND", "F NAO - MAO", "F ENG S F NAO - MAO")
    h.adjudicate()

    for spec in ("F MAO", "F IRI", "A BRE"):
        assert h._result_at(spec).result is ResultCode.NO_CONVOY, spec
    # The support that matters, and its consequence.
    assert h._result_at("F WES").result is ResultCode.OK
    h.assert_bounce("F NAO")
    assert h.dislodged_provinces() == set(), "nothing should be dislodged"
    assert h.unit_powers_at("MAO") == "FRANCE"
    assert h.unit_powers_at("BRE") == "FRANCE"
    assert h.unit_powers_at("CLY") is None
