"""
Tests for precomputed allowed moves: direct moves and convoy reachability.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from engine.map import Map
from engine.allowed_moves import (
    build_direct_moves,
    build_convoy_reachable,
    build_convoy_reachable_by_source,
    build_allowed_moves,
    AllowedMoves,
    MULTI_COAST_PROVINCES,
)


@pytest.fixture
def standard_map():
    return Map("standard")


class TestBuildDirectMoves:
    """Test build_direct_moves from Map."""

    def test_returns_dict_with_tuple_keys(self, standard_map):
        direct = build_direct_moves(standard_map)
        assert isinstance(direct, dict)
        for k in direct:
            assert isinstance(k, tuple)
            assert len(k) in (2, 3)
            assert k[0] in standard_map.provinces
            assert k[1] in ("A", "F")

    def test_army_in_paris_has_moves(self, standard_map):
        direct = build_direct_moves(standard_map)
        key = ("PAR", "A")
        assert key in direct
        targets = direct[key]
        assert "BUR" in targets or "GAS" in targets or "BRE" in targets
        for t in targets:
            assert t in standard_map.provinces

    def test_fleet_in_eng_channel_has_sea_and_coastal(self, standard_map):
        direct = build_direct_moves(standard_map)
        key = ("ENG", "F")
        assert key in direct
        targets = direct[key]
        assert "BRE" in targets or "LON" in targets or "MAO" in targets or "NTH" in targets

    def test_multi_coast_fleet_has_coast_specific_keys(self, standard_map):
        direct = build_direct_moves(standard_map)
        for prov in MULTI_COAST_PROVINCES:
            if prov not in standard_map.provinces:
                continue
            for coast in ("NC", "SC", "EC"):
                key = (prov, "F", coast)
                if key in direct:
                    assert isinstance(direct[key], list)

    def test_stp_nc_fleet_only_reaches_bar_nwg(self, standard_map):
        direct = build_direct_moves(standard_map)
        key = ("STP", "F", "NC")
        if key in direct:
            targets = direct[key]
            assert "BAR" in targets or "NWG" in targets
            for t in targets:
                assert t in ("BAR", "NWG")


class TestBuildConvoyReachable:
    """Test convoy reachability (coastal -> coastal by sea path)."""

    def test_returns_set_of_pairs(self, standard_map):
        reachable = build_convoy_reachable(standard_map)
        assert isinstance(reachable, set)
        for pair in reachable:
            assert len(pair) == 2
            assert isinstance(pair[0], str) and isinstance(pair[1], str)

    def test_symmetric_connectivity(self, standard_map):
        reachable = build_convoy_reachable(standard_map)
        for (a, b) in reachable:
            assert (b, a) in reachable or a == b

    def test_no_self_pairs(self, standard_map):
        reachable = build_convoy_reachable(standard_map)
        for (a, b) in reachable:
            assert a != b

    def test_england_france_convoy_reachable(self, standard_map):
        reachable = build_convoy_reachable(standard_map)
        # LON (London) and BRE (Brest) are both coastal and connected via ENG/MAO
        coastal = {p for p, prov in standard_map.provinces.items() if prov.type == "coastal"}
        assert "LON" in coastal and "BRE" in coastal
        assert ("LON", "BRE") in reachable or ("BRE", "LON") in reachable

    def test_by_source_is_consistent_with_set(self, standard_map):
        reachable = build_convoy_reachable(standard_map)
        by_src = build_convoy_reachable_by_source(standard_map)
        for (from_c, to_c) in reachable:
            assert from_c in by_src
            assert to_c in by_src[from_c]


class TestAllowedMovesClass:
    """Test AllowedMoves container and helpers."""

    def test_build_allowed_moves_from_map(self, standard_map):
        am = build_allowed_moves(standard_map)
        assert am.map_name == "standard"
        assert isinstance(am.direct_moves, dict)
        assert isinstance(am.convoy_reachable, set)

    def test_get_direct_targets_army(self, standard_map):
        am = build_allowed_moves(standard_map)
        targets = am.get_direct_targets("PAR", "A")
        assert isinstance(targets, list)
        assert "BUR" in targets or "GAS" in targets or "BRE" in targets

    def test_get_direct_targets_fleet_multi_coast(self, standard_map):
        am = build_allowed_moves(standard_map)
        targets_nc = am.get_direct_targets("STP", "F", "NC")
        targets_sc = am.get_direct_targets("STP", "F", "SC")
        assert "BAR" in targets_nc or "NWG" in targets_nc
        assert "FIN" in targets_sc or "BOT" in targets_sc or "LVN" in targets_sc

    def test_is_direct_move_allowed(self, standard_map):
        am = build_allowed_moves(standard_map)
        assert am.is_direct_move_allowed("PAR", "BUR", "A") is True
        assert am.is_direct_move_allowed("PAR", "LON", "A") is False

    def test_is_convoy_reachable(self, standard_map):
        am = build_allowed_moves(standard_map)
        # Some coastal pair must be reachable
        assert len(am.convoy_reachable) > 0
        first = next(iter(am.convoy_reachable))
        assert am.is_convoy_reachable(first[0], first[1]) is True

    def test_get_convoy_targets(self, standard_map):
        am = build_allowed_moves(standard_map)
        for from_c, to_list in am.convoy_reachable_by_source.items():
            assert am.get_convoy_targets(from_c) == to_list

    def test_to_dict_serializable(self, standard_map):
        am = build_allowed_moves(standard_map)
        d = am.to_dict()
        assert "map_name" in d
        assert "direct_moves" in d
        assert "convoy_reachable" in d
        for k, v in d["direct_moves"].items():
            assert "|" in k or k.count("|") >= 1
            assert isinstance(v, list)


class TestIntegrationWithGame:
    """Test that Game builds allowed_moves and validation uses it."""

    def test_game_state_has_allowed_moves(self):
        from engine.game import Game
        game = Game(map_name="standard")
        assert game.game_state.allowed_moves is not None
        assert isinstance(game.game_state.allowed_moves, AllowedMoves)

    def test_move_order_validation_uses_allowed_moves(self):
        from engine.game import Game
        from engine.data_models import MoveOrder, Unit
        game = Game(map_name="standard")
        game.add_player("FRANCE")
        # Add a unit so we can submit an order
        from engine.data_models import PowerState
        game.game_state.powers["FRANCE"] = PowerState(
            power_name="FRANCE",
            units=[Unit("A", "PAR", "FRANCE")],
            controlled_supply_centers=["PAR"],
            home_supply_centers=["PAR"],
            is_eliminated=False,
            orders_submitted=False,
        )
        game.game_state.orders["FRANCE"] = []
        order = MoveOrder(power="FRANCE", unit=Unit("A", "PAR", "FRANCE"), target_province="BUR")
        valid, msg = order.validate(game.game_state)
        assert valid is True, msg
        order_bad = MoveOrder(power="FRANCE", unit=Unit("A", "PAR", "FRANCE"), target_province="LON")
        valid_bad, msg_bad = order_bad.validate(game.game_state)
        assert valid_bad is False
