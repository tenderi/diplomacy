"""M1 topology tests: the loaded ``standard.map`` matches the board exactly."""

from __future__ import annotations

import pytest

from engine.map_loader import load_standard_map
from engine.types import Location, ProvinceType, Season, Unit, UnitKind

pytestmark = pytest.mark.map


@pytest.fixture(scope="module")
def m():
    return load_standard_map()


# -- counts -----------------------------------------------------------------


def test_province_count(m):
    assert len(m.provinces) == 75


def test_supply_center_count(m):
    assert len(m.supply_centers) == 34


def test_home_center_totals(m):
    # 22 home centers across the seven powers.
    total = sum(len(v) for v in m.home_centers.values())
    assert total == 22
    assert set(m.home_centers) == {
        "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY",
    }
    assert m.home_centers["RUSSIA"] == frozenset({"MOS", "SEV", "STP", "WAR"})
    assert m.home_centers["FRANCE"] == frozenset({"BRE", "MAR", "PAR"})


def test_neutral_supply_centers_present(m):
    neutrals = {"BEL", "BUL", "DEN", "GRE", "HOL", "NWY", "POR", "RUM", "SER", "SPA", "SWE", "TUN"}
    assert neutrals <= m.supply_centers
    # neutrals are not owned at the start
    for n in neutrals:
        assert n not in m.initial_ownership


def test_switzerland_impassable(m):
    # SWI is referenced as a neighbour but has no ABUTS line → dropped entirely.
    assert "SWI" not in m.provinces
    assert "SWI" not in m.army_moves("BUR")
    assert "SWI" not in m.army_moves("MUN")


# -- province types ---------------------------------------------------------


def test_province_types(m):
    assert m.province_type("PAR") is ProvinceType.LAND
    assert m.province_type("BRE") is ProvinceType.COAST
    assert m.province_type("NTH") is ProvinceType.WATER
    assert m.province_type("BUL") is ProvinceType.COAST


# -- start position ---------------------------------------------------------


def test_start_phase(m):
    assert m.start_year == 1901
    assert m.start_season is Season.SPRING


def test_starting_units(m):
    expected = {
        Unit(UnitKind.ARMY, "AUSTRIA", Location("BUD")),
        Unit(UnitKind.ARMY, "AUSTRIA", Location("VIE")),
        Unit(UnitKind.FLEET, "AUSTRIA", Location("TRI")),
        Unit(UnitKind.FLEET, "ENGLAND", Location("EDI")),
        Unit(UnitKind.FLEET, "ENGLAND", Location("LON")),
        Unit(UnitKind.ARMY, "ENGLAND", Location("LVP")),
        Unit(UnitKind.FLEET, "FRANCE", Location("BRE")),
        Unit(UnitKind.ARMY, "FRANCE", Location("MAR")),
        Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
        Unit(UnitKind.FLEET, "GERMANY", Location("KIE")),
        Unit(UnitKind.ARMY, "GERMANY", Location("BER")),
        Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
        Unit(UnitKind.FLEET, "ITALY", Location("NAP")),
        Unit(UnitKind.ARMY, "ITALY", Location("ROM")),
        Unit(UnitKind.ARMY, "ITALY", Location("VEN")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("WAR")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("MOS")),
        Unit(UnitKind.FLEET, "RUSSIA", Location("SEV")),
        Unit(UnitKind.FLEET, "RUSSIA", Location("STP", "SC")),
        Unit(UnitKind.FLEET, "TURKEY", Location("ANK")),
        Unit(UnitKind.ARMY, "TURKEY", Location("CON")),
        Unit(UnitKind.ARMY, "TURKEY", Location("SMY")),
    }
    assert m.starting_units == frozenset(expected)
    assert len(m.starting_units) == 22


def test_russia_starts_with_stp_south_coast(m):
    stp_fleet = [u for u in m.starting_units if u.province == "STP"]
    assert len(stp_fleet) == 1
    assert stp_fleet[0].location == Location("STP", "SC")


# -- split-coast fleet adjacency (exact) ------------------------------------


def _fmoves(m, prov, coast):
    return m.fleet_moves(Location(prov, coast))


def test_bulgaria_coasts(m):
    assert m.coasts_of("BUL") == ("EC", "SC")
    assert _fmoves(m, "BUL", "EC") == {Location("BLA"), Location("CON"), Location("RUM")}
    assert _fmoves(m, "BUL", "SC") == {Location("AEG"), Location("CON"), Location("GRE")}
    # A fleet cannot occupy Bulgaria without naming a coast: no bare fleet node.
    assert m.fleet_moves(Location("BUL")) == frozenset()


def test_spain_coasts(m):
    assert m.coasts_of("SPA") == ("NC", "SC")
    assert _fmoves(m, "SPA", "NC") == {Location("GAS"), Location("MAO"), Location("POR")}
    assert _fmoves(m, "SPA", "SC") == {
        Location("LYO"), Location("MAO"), Location("MAR"), Location("POR"), Location("WES"),
    }


def test_stp_coasts(m):
    assert m.coasts_of("STP") == ("NC", "SC")
    assert _fmoves(m, "STP", "NC") == {Location("BAR"), Location("NWY")}
    assert _fmoves(m, "STP", "SC") == {Location("BOT"), Location("FIN"), Location("LVN")}


def test_bulgaria_army_ignores_coasts(m):
    # An army in Bulgaria uses the bare node: all non-water neighbours.
    assert m.army_moves("BUL") == {"CON", "GRE", "RUM", "SER"}


# -- army vs fleet passability (case rule) ----------------------------------


def test_ankara_army_can_reach_smyrna_fleet_cannot(m):
    assert "SMY" in m.army_moves("ANK")
    assert Location("SMY") not in m.fleet_moves(Location("ANK"))
    assert m.fleet_moves(Location("ANK")) == {Location("ARM"), Location("BLA"), Location("CON")}


def test_edinburgh_army_can_reach_liverpool_fleet_cannot(m):
    assert "LVP" in m.army_moves("EDI")
    assert Location("LVP") not in m.fleet_moves(Location("EDI"))


def test_venice_fleet_limited_to_shared_coastline(m):
    # Army Venice reaches six neighbours; fleet Venice only Adriatic/Apulia/Trieste.
    assert m.army_moves("VEN") == {"APU", "PIE", "ROM", "TRI", "TUS", "TYR"}
    assert m.fleet_moves(Location("VEN")) == {Location("ADR"), Location("APU"), Location("TRI")}


# -- symmetry ---------------------------------------------------------------


def test_army_adjacency_symmetric(m):
    for prov, dests in m._army_adj.items():
        for d in dests:
            assert prov in m.army_moves(d), f"army edge {prov}->{d} not symmetric"


def test_fleet_adjacency_symmetric(m):
    for loc, dests in m._fleet_adj.items():
        for d in dests:
            assert loc in m.fleet_moves(d), f"fleet edge {loc}->{d} not symmetric"


def test_no_army_edges_into_water(m):
    for prov, dests in m._army_adj.items():
        for d in dests:
            assert m.province_type(d) is not ProvinceType.WATER


def test_no_fleet_edges_into_land(m):
    for loc, dests in m._fleet_adj.items():
        for d in dests:
            assert m.province_type(d.province) is not ProvinceType.LAND
