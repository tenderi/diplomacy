"""Convoy paradoxes found by a differential fuzz, pinned with their Szykman results.

Each board comes from a random convoy-board generator (the fuzz run on PR #187;
the seed numbers are kept as ids). In every one, a convoyed army's attack would
cut a support that decides whether one of its own convoying fleets is dislodged:
the shape of DATC 6.F.14 (the support helps an attack on the fleet) or 6.F.18
(the support holds the fleet, or gives prevent strength against its attacker).
Each has two consistent outcomes or none. The Szykman rule settles it: the
convoy fails (``NO_CONVOY``), the support stands, and the rest follows.

The first ten gave different results under different submission orders before
BC5; the next seven gave one result, but not Szykman's (the convoying fleet
dislodged). The last three (seeds from ``tests/datc/convoy_boards.py``) moved two
units into one province on some orders; 109034 is also the rare board on which
a cycle's second guess reaches a guess further up the call stack. The expected results were checked by hand; each board is adjudicated
under its own order, reversed and in seeded shuffles.
"""

from __future__ import annotations

import random

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = [pytest.mark.datc]

# seed -> [(power, order, result, dislodged)], one line per unit.
_BOARDS: dict[int, list[tuple[str, str, str, bool]]] = {
    1105: [
        ("FRANCE", "F ADR - ION", "BOUNCE", False),
        ("FRANCE", "F AEG - GRE", "BOUNCE", False),
        ("ENGLAND", "F ALB - ION", "BOUNCE", False),
        ("ENGLAND", "F ANK H", "OK", False),
        ("GERMANY", "A BUL S A NAP - GRE", "OK", False),
        ("FRANCE", "A CON - SMY", "BOUNCE", False),
        ("FRANCE", "F EAS S F ADR - ION", "OK", False),
        ("FRANCE", "F GRE S F ALB - ION", "OK", False),
        ("GERMANY", "F ION C A NAP - GRE", "OK", False),
        ("FRANCE", "F LYO C A NAF - SPA", "OK", False),
        ("GERMANY", "A MAR H", "OK", False),
        ("ENGLAND", "A NAF - SPA", "BOUNCE", False),
        ("GERMANY", "A NAP - GRE", "NO_CONVOY", False),
        ("ENGLAND", "A PIE S A MAR", "OK", False),
        ("GERMANY", "F ROM - NAP", "BOUNCE", False),
        ("ENGLAND", "A SMY S F SYR", "CUT", False),
        ("ENGLAND", "F SPA/SC - WES", "BOUNCE", False),
        ("GERMANY", "F SYR H", "OK", False),
        ("ENGLAND", "A TRI - TYR", "OK", False),
        ("FRANCE", "F TUN S F SPA - WES", "VOID", False),
        ("FRANCE", "F TUS - LYO", "BOUNCE", False),
        ("GERMANY", "A TYR - MUN", "OK", False),
        ("ENGLAND", "F TYS - NAP", "BOUNCE", False),
        ("FRANCE", "F WES C A NAF - SPA", "OK", False),
    ],
    3589: [
        ("FRANCE", "F BEL - ENG", "BOUNCE", False),
        ("ENGLAND", "F ENG C A PIC - LON", "OK", False),
        ("GERMANY", "F IRI S F NTH - ENG", "OK", False),
        ("FRANCE", "F LON S F BEL - ENG", "OK", False),
        ("FRANCE", "A LVP - WAL", "OK", False),
        ("FRANCE", "F MAO - GAS", "OK", False),
        ("GERMANY", "F NAO - MAO", "OK", False),
        ("FRANCE", "F NTH - ENG", "BOUNCE", False),
        ("FRANCE", "F NWG - NTH", "BOUNCE", False),
        ("ENGLAND", "A PIC - LON", "NO_CONVOY", False),
        ("ENGLAND", "F WES H", "OK", False),
    ],
    4958: [
        ("ENGLAND", "F BEL S F LON - NTH", "VOID", False),
        ("ENGLAND", "A BUR S F BEL", "OK", False),
        ("FRANCE", "F EDI S F LON - NTH", "OK", False),
        ("FRANCE", "F ENG - MAO", "OK", False),
        ("FRANCE", "F HEL C A YOR - EDI", "VOID", False),
        ("FRANCE", "F HOL - NTH", "BOUNCE", False),
        ("FRANCE", "F LON - NTH", "OK", False),
        ("ENGLAND", "F NTH C A YOR - EDI", "DISLODGED", True),
        ("ENGLAND", "F NWG C A YOR - EDI", "NO_CONVOY", False),
        ("FRANCE", "F NWY - NWG", "BOUNCE", False),
        ("ENGLAND", "A PIC S F BEL", "OK", False),
        ("FRANCE", "A RUH H", "OK", False),
        ("ENGLAND", "F SKA - NWY", "BOUNCE", False),
        ("ENGLAND", "A YOR - EDI VIA", "NO_CONVOY", False),
    ],
    5904: [
        ("ENGLAND", "A ARM - CON", "NO_CONVOY", False),
        ("ENGLAND", "F BLA C A ARM - CON", "DISLODGED", True),
        ("FRANCE", "A BUD S A UKR - GAL", "OK", False),
        ("GERMANY", "F CON S F SEV - BLA", "OK", False),
        ("GERMANY", "F RUM - BLA", "BOUNCE", False),
        ("ENGLAND", "A SER S A BUD", "OK", False),
        ("GERMANY", "F SEV - BLA", "OK", False),
        ("GERMANY", "A SMY - CON", "BOUNCE", False),
        ("ENGLAND", "A UKR - GAL", "OK", False),
    ],
    6250: [
        ("TURKEY", "A BEL - NWY", "NO_CONVOY", False),
        ("GERMANY", "A EDI H", "OK", False),
        ("ENGLAND", "F ENG - NTH", "OK", False),
        ("ITALY", "F HEL - NTH", "BOUNCE", False),
        ("ENGLAND", "F HOL S F ENG - NTH", "CUT", False),
        ("ITALY", "F IRI - ENG", "OK", False),
        ("ITALY", "A KIE - HOL", "BOUNCE", False),
        ("TURKEY", "F LON S F ENG - NTH", "VOID", False),
        ("FRANCE", "F MAO - IRI", "OK", False),
        ("TURKEY", "F NTH C A BEL - NWY", "DISLODGED", True),
        ("FRANCE", "F NWY S F ENG - NTH", "OK", False),
        ("TURKEY", "F PIC S F IRI - ENG", "OK", False),
        ("ENGLAND", "F SKA C A BEL - NWY", "NO_CONVOY", False),
        ("ITALY", "A YOR S F LON", "OK", False),
    ],
    10884: [
        ("GERMANY", "F BAR - NWY", "BOUNCE", False),
        ("ENGLAND", "A BEL - HOL VIA", "NO_CONVOY", False),
        ("ITALY", "A CLY - LVP", "BOUNCE", False),
        ("ENGLAND", "A DEN H", "OK", False),
        ("ITALY", "F ENG C A BEL - HOL", "DISLODGED", True),
        ("GERMANY", "F HEL C A BEL - HOL", "NO_CONVOY", False),
        ("ITALY", "F HOL S F SKA - NTH", "OK", False),
        ("GERMANY", "F IRI S F MAO - ENG", "OK", False),
        ("ITALY", "A LVP H", "OK", False),
        ("GERMANY", "F MAO - ENG", "OK", False),
        ("ENGLAND", "F NTH C A BEL - HOL", "DISLODGED", True),
        ("ITALY", "F NWG C A BEL - CLY", "VOID", False),
        ("FRANCE", "A NWY H", "OK", False),
        ("GERMANY", "F SKA - NTH", "OK", False),
        ("ENGLAND", "A STP S A NWY", "OK", False),
        ("ITALY", "F YOR - NTH", "BOUNCE", False),
    ],
    22626: [
        ("GERMANY", "A BRE - POR", "NO_CONVOY", False),
        ("GERMANY", "F ENG - MAO", "BOUNCE", False),
        ("FRANCE", "F IRI - MAO", "OK", False),
        ("ENGLAND", "F MAO C A BRE - POR", "DISLODGED", True),
        ("FRANCE", "F NTH - ENG", "BOUNCE", False),
        ("GERMANY", "F PIC - ENG", "BOUNCE", False),
        ("FRANCE", "F POR S F IRI - MAO", "OK", False),
    ],
    23226: [
        ("GERMANY", "F DEN S F HEL - NTH", "OK", False),
        ("ITALY", "F EDI H", "OK", False),
        ("GERMANY", "F ENG C A LON - PIC", "OK", False),
        ("ITALY", "F HEL - NTH", "OK", False),
        ("GERMANY", "F HOL - NTH", "BOUNCE", False),
        ("FRANCE", "A LON - PIC", "OK", False),
        ("FRANCE", "F NAO S F NWG", "OK", False),
        ("FRANCE", "F NTH C A NWY - DEN", "DISLODGED", True),
        ("FRANCE", "F NWG C A NWY - DEN", "NO_CONVOY", False),
        ("FRANCE", "A NWY - DEN", "NO_CONVOY", False),
        ("ENGLAND", "F SKA - NWY", "BOUNCE", False),
    ],
    26956: [
        ("ENGLAND", "F ANK - BLA", "BOUNCE", False),
        ("FRANCE", "A ARM - SEV VIA", "NO_CONVOY", False),
        ("FRANCE", "F BLA C A ARM - SEV", "DISLODGED", True),
        ("FRANCE", "A BUL - GRE", "OK", False),
        ("ENGLAND", "F CON - BLA", "OK", False),
        ("FRANCE", "F RUM S F CON - BLA", "VOID", False),
        ("ENGLAND", "F SEV S F CON - BLA", "OK", False),
    ],
    37386: [
        ("ENGLAND", "F ADR S F EAS - ION", "OK", False),
        ("ITALY", "F ALB - ION", "BOUNCE", False),
        ("ITALY", "F APU S F ALB - ION", "OK", False),
        ("FRANCE", "F EAS - ION", "BOUNCE", False),
        ("GERMANY", "F ION C A NAP - APU", "OK", False),
        ("FRANCE", "A NAP - APU VIA", "NO_CONVOY", False),
        ("FRANCE", "A SMY - SYR", "OK", False),
        ("GERMANY", "F TUS - TYS", "BOUNCE", False),
        ("GERMANY", "F TYS C A NAP - APU", "NO_CONVOY", False),
    ],
    1088: [
        ("FRANCE", "F BAR - NWY", "OK", False),
        ("ITALY", "F DEN S F HEL - NTH", "OK", False),
        ("FRANCE", "F EDI S F NTH", "OK", False),
        ("GERMANY", "F ENG H", "OK", False),
        ("GERMANY", "F HEL - NTH", "BOUNCE", False),
        ("GERMANY", "A HOL - RUH", "OK", False),
        ("FRANCE", "F NTH C A SWE - EDI", "OK", False),
        ("FRANCE", "F NWG S F HEL - NTH", "VOID", False),
        ("ENGLAND", "F SKA C A SWE - EDI", "NO_CONVOY", False),
        ("ITALY", "A SWE - EDI", "NO_CONVOY", False),
    ],
    11230: [
        ("ENGLAND", "A BEL - EDI", "NO_CONVOY", False),
        ("FRANCE", "F DEN - NTH", "BOUNCE", False),
        ("GERMANY", "F EDI S F SKA - NTH", "VOID", False),
        ("FRANCE", "F HEL C A BEL - EDI", "VOID", False),
        ("GERMANY", "F NTH C A BEL - EDI", "OK", False),
        ("ENGLAND", "F NWG S F DEN - NTH", "OK", False),
        ("ENGLAND", "F SKA - NTH", "BOUNCE", False),
    ],
    23374: [
        ("ITALY", "F ADR C A TUN - NAP", "VOID", False),
        ("FRANCE", "F AEG C A BUL - GRE", "OK", False),
        ("ENGLAND", "F ALB S F EAS - ION", "OK", False),
        ("ITALY", "A BUL - GRE", "BOUNCE", False),
        ("ENGLAND", "F EAS - ION", "BOUNCE", False),
        ("ENGLAND", "F GRE - AEG", "BOUNCE", False),
        ("ITALY", "F ION C A TUN - NAP", "OK", False),
        ("ENGLAND", "A NAF - TUN", "BOUNCE", False),
        ("FRANCE", "F NAP S F ION", "OK", False),
        ("ENGLAND", "A SYR H", "OK", False),
        ("GERMANY", "A TRI S F ALB", "OK", False),
        ("GERMANY", "A TUN - NAP", "NO_CONVOY", False),
    ],
    25817: [
        ("FRANCE", "A BEL - WAL", "NO_CONVOY", False),
        ("FRANCE", "F BRE - ENG", "BOUNCE", False),
        ("GERMANY", "F ENG C A BEL - WAL", "OK", False),
        ("FRANCE", "F HOL - BEL", "BOUNCE", False),
        ("ENGLAND", "F NTH S F BRE - ENG", "OK", False),
        ("FRANCE", "F NWG S F NTH", "OK", False),
        ("GERMANY", "F WAL S F ENG", "OK", False),
    ],
    29241: [
        ("FRANCE", "F ION C A ROM - TUN", "NO_CONVOY", False),
        ("GERMANY", "F LYO - TYS", "BOUNCE", False),
        ("GERMANY", "F MAR - SPA/SC", "BOUNCE", False),
        ("FRANCE", "A NAF H", "OK", False),
        ("GERMANY", "F NAP - TYS", "BOUNCE", False),
        ("GERMANY", "A ROM - TUN", "NO_CONVOY", False),
        ("GERMANY", "F SPA/SC H", "OK", False),
        ("ENGLAND", "F TUN S F NAP - TYS", "VOID", False),
        ("ENGLAND", "A TUS H", "OK", False),
        ("ENGLAND", "F TYS C A ROM - TUN", "OK", False),
        ("FRANCE", "F WES S F LYO - TYS", "OK", False),
    ],
    31831: [
        ("ENGLAND", "F ADR S F TYS - ION", "OK", False),
        ("ITALY", "F AEG H", "OK", False),
        ("ITALY", "F ALB - ION", "BOUNCE", False),
        ("FRANCE", "A APU H", "OK", False),
        ("ITALY", "A CON - SMY", "BOUNCE", False),
        ("FRANCE", "F EAS C A SMY - TUN", "NO_CONVOY", False),
        ("GERMANY", "A GRE H", "OK", False),
        ("ITALY", "F ION C A SMY - TUN", "OK", False),
        ("FRANCE", "A SMY - TUN", "NO_CONVOY", False),
        ("ENGLAND", "F TUN S F ALB - ION", "OK", False),
        ("FRANCE", "F TYS - ION", "BOUNCE", False),
    ],
    36543: [
        ("ENGLAND", "F BEL S F NWG - NTH", "OK", False),
        ("FRANCE", "A DEN - EDI", "NO_CONVOY", False),
        ("ENGLAND", "F EDI S F NTH", "OK", False),
        ("ENGLAND", "F ENG C A DEN - EDI", "VOID", False),
        ("ENGLAND", "F HEL C A KIE - DEN", "OK", False),
        ("GERMANY", "A KIE - DEN VIA", "BOUNCE", False),
        ("ENGLAND", "A LON H", "OK", False),
        ("GERMANY", "F NTH C A DEN - EDI", "OK", False),
        ("ENGLAND", "F NWG - NTH", "BOUNCE", False),
        ("ENGLAND", "F SKA C A DEN - EDI", "NO_CONVOY", False),
    ],
    109034: [
        ("ITALY", "F ADR S F TYS - ION", "OK", False),
        ("ENGLAND", "A ALB - TUN", "NO_CONVOY", False),
        ("ITALY", "F APU - NAP", "BOUNCE", False),
        ("ITALY", "A BUD H", "OK", False),
        ("ITALY", "F EAS C A ALB - TUN", "VOID", False),
        ("ENGLAND", "F ION C A ALB - TUN", "OK", False),
        ("ITALY", "F NAP - ION", "BOUNCE", False),
        ("ENGLAND", "A SER - ALB", "BOUNCE", False),
        ("FRANCE", "F SMY - EAS", "BOUNCE", False),
        ("GERMANY", "A SYR - SMY", "BOUNCE", False),
        ("ITALY", "F TUN S F NAP - ION", "OK", False),
        ("ITALY", "A TYR - MUN", "OK", False),
        ("FRANCE", "F TYS - ION", "BOUNCE", False),
    ],
    113342: [
        ("FRANCE", "F BAR - NWG", "BOUNCE", False),
        ("GERMANY", "F EDI S F NAO - NWG", "OK", False),
        ("FRANCE", "F LVP - WAL", "OK", False),
        ("FRANCE", "F NAO - NWG", "OK", False),
        ("ENGLAND", "F NWG C A NWY - EDI", "DISLODGED", True),
        ("ENGLAND", "A NWY - EDI", "NO_CONVOY", False),
    ],
    135644: [
        ("ITALY", "A ANK - CON VIA", "NO_CONVOY", False),
        ("GERMANY", "F ARM - BLA", "BOUNCE", False),
        ("FRANCE", "F BLA C A ANK - CON", "DISLODGED", True),
        ("GERMANY", "F BUL/EC - BLA", "OK", False),
        ("ENGLAND", "F CON S F BUL - BLA", "OK", False),
    ],
}


def _harness(board: list[tuple[str, str, str, bool]]) -> Harness:
    h = Harness()
    for power, order, _, _ in board:
        h.units(power, " ".join(order.split()[:2]))
        h.orders(power, order)
    return h


@pytest.mark.parametrize("seed", sorted(_BOARDS))
def test_szykman_board(seed: int) -> None:
    board = _BOARDS[seed]
    h = _harness(board)
    given = list(h._orders)
    orderings = [given, given[::-1]]
    for k in range(20):
        shuffled = list(given)
        random.Random(k).shuffle(shuffled)
        orderings.append(shuffled)
    for ordering in orderings:
        h._orders = ordering
        h.adjudicate()
        for _, order, result, dislodged in board:
            unit = " ".join(order.split()[:2])
            h.assert_result(unit, ResultCode[result])
            if dislodged:
                h.assert_dislodged(unit)
            else:
                h.assert_not_dislodged(unit)
