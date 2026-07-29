"""M6 checkpoint A: the new-engine game service over state_json persistence."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from persistence.game_repo import GameRepo
from rendering.map import Map
from rendering.order_overlay import orders_by_power_to_viz, resolution_dict_to_viz
from rendering.view_adapter import phase_info as build_phase_info
from rendering.view_adapter import svg_path_for_map_name, units_for_render
from server.game_service import GameService

pytestmark = pytest.mark.database

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_NONTRIVIAL_PNG_BYTES = 5000  # a bare/near-empty board renders far smaller than this


@pytest.fixture
def service(temp_db):
    """A GameService bound to the test database."""
    session_factory = sessionmaker(bind=temp_db)
    return GameService(GameRepo(session_factory))


def _new_game(service) -> str:
    gid = f"gs-{uuid.uuid4().hex[:8]}"
    service.create_game(gid)
    return gid


def _kind_by_province(view: dict) -> dict:
    return {
        u["location"].split("/")[0]: u["kind"]
        for units in view["units_by_power"].values()
        for u in units
    }


def _render_resolution_png(service: GameService, gid: str) -> bytes:
    """Mirror ``server.api.routes.maps.generate_resolution_map`` without the
    FastAPI/db_service layer: render the board for whatever phase is current,
    with arrows for the last processed phase's resolution."""
    view = service.view(gid)
    resolution = service.last_resolution(gid)
    order_viz = resolution_dict_to_viz(resolution, _kind_by_province(view))
    svg_path = svg_path_for_map_name(view["map_name"])
    return Map.render_board_png_resolution(
        svg_path,
        units_for_render(view),
        order_viz,
        {"conflicts": [{"province": p, "result": "standoff"} for p in view["contested"]]},
        phase_info=build_phase_info(view, 0),
        supply_center_control=dict(view["ownership"]),
    )


class TestLifecycle:
    def test_create_and_view_opening(self, service):
        gid = _new_game(service)
        v = service.view(gid)
        assert v is not None
        assert v["phase"] == "S1901M"
        assert v["phase_type"] == "MOVEMENT"
        assert len(v["units"]) == 22
        assert v["ownership"]["PAR"] == "FRANCE"
        assert v["status"] == "ACTIVE"

    def test_submit_orders_validates(self, service):
        gid = _new_game(service)
        results = service.submit_orders(gid, "FRANCE", ["A PAR - BUR", "A PAR - MOS"])
        assert results[0]["ok"] is True  # PAR adjacent to BUR
        assert results[1]["ok"] is False  # PAR not adjacent to MOS
        v = service.view(gid)
        assert "FRANCE" in v["orders"]
        assert v["orders"]["FRANCE"] == ["A PAR - BUR"]  # only the legal one stored

    def test_process_turn_advances_phase(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR"])
        out = service.process_turn(gid)
        assert out["phase"] == "F1901M"  # all-hold-ish spring -> fall movement
        v = service.view(gid)
        assert v["phase"] == "F1901M"
        assert v["orders"] == {}  # pending cleared
        # France's Paris army advanced to Burgundy.
        provinces = {u["location"] for u in v["units"] if u["power"] == "FRANCE"}
        assert "BUR" in provinces and "PAR" not in provinces

    def test_coasted_fleet_move(self, service):
        gid = _new_game(service)
        # Russia's fleet at STP/SC can move to BOT (Gulf of Bothnia).
        results = service.submit_orders(gid, "RUSSIA", ["F STP/SC - BOT"])
        assert results[0]["ok"] is True

    def test_load_missing_game_returns_none(self, service):
        assert service.load("does-not-exist") is None
        assert service.view("does-not-exist") is None


class TestResolutionPersistence:
    """process_turn stores the adjudication for later resolution-map rendering."""

    def test_last_resolution_none_before_first_turn(self, service):
        gid = _new_game(service)
        assert service.last_resolution(gid) is None

    def test_process_turn_persists_resolution(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR"])
        service.process_turn(gid)
        res = service.last_resolution(gid)
        assert res is not None
        assert "results" in res and len(res["results"]) >= 1
        # The stored resolution round-trips through serialization and names the move.
        moves = [
            r for r in res["results"]
            if r["order"].get("type") == "MOVE" and r["order"].get("dest") == "BUR"
        ]
        assert moves and moves[0]["result"] == "OK"

    def test_pending_orders_parsed_roundtrips(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR", "A MAR S A PAR - BUR"])
        parsed = service.pending_orders_parsed(gid)
        assert set(parsed.keys()) == {"FRANCE"}
        assert len(parsed["FRANCE"]) == 2


class TestOrderDisplay:
    """view() echoes pending orders with unit letters matching the board."""

    def test_fleet_at_non_split_province_displays_as_fleet(self, service):
        gid = _new_game(service)
        # France's fleet sits at BRE, a non-split-coast province. Stored via
        # format_order it would read "A BRE H"; the view must correct it to "F".
        service.submit_orders(gid, "FRANCE", ["F BRE H"])
        v = service.view(gid)
        assert v["orders"]["FRANCE"] == ["F BRE H"]

    def test_army_order_still_displays_as_army(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR"])
        v = service.view(gid)
        assert v["orders"]["FRANCE"] == ["A PAR - BUR"]


class TestOrderHistory:
    """process_turn accumulates submitted orders into a per-turn history."""

    def test_history_empty_before_first_turn(self, service):
        gid = _new_game(service)
        assert service.order_history(gid) == {}

    def test_history_accumulates_per_turn_with_truthful_letters(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR", "F BRE H"])
        service.submit_orders(gid, "GERMANY", ["A MUN - RUH"])
        service.process_turn(gid)  # records turn 0
        service.submit_orders(gid, "FRANCE", ["A BUR - MAR"])
        service.process_turn(gid)  # records turn 1

        history = service.order_history(gid)
        assert set(history.keys()) == {"0", "1"}
        # Fleet at a non-split province is recorded as F, not A.
        assert history["0"]["FRANCE"] == ["A PAR - BUR", "F BRE H"]
        assert history["0"]["GERMANY"] == ["A MUN - RUH"]
        assert history["1"]["FRANCE"] == ["A BUR - MAR"]

    def test_history_skips_powers_with_no_orders(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR"])
        service.process_turn(gid)
        assert list(service.order_history(gid)["0"].keys()) == ["FRANCE"]


class TestMapRenderingSmoke:
    """V4 end-to-end smoke test: create -> submit -> orders map -> process ->
    resolution map, on the standard opening. Extends the resolution-persistence
    coverage above with the actual PNG-rendering leg of the pipeline."""

    def test_create_submit_orders_map_process_resolution_map(self, service):
        gid = _new_game(service)
        service.submit_orders(gid, "FRANCE", ["A PAR - BUR", "A MAR S A PAR - BUR"])
        service.submit_orders(gid, "GERMANY", ["A MUN H"])

        view = service.view(gid)
        order_viz = orders_by_power_to_viz(
            service.pending_orders_parsed(gid), _kind_by_province(view)
        )
        svg_path = svg_path_for_map_name(view["map_name"])
        orders_png = Map.render_board_png_orders(
            svg_path,
            units_for_render(view),
            order_viz,
            phase_info=build_phase_info(view, 0),
            supply_center_control=dict(view["ownership"]),
        )
        assert orders_png[:8] == _PNG_MAGIC
        assert len(orders_png) > _NONTRIVIAL_PNG_BYTES

        service.process_turn(gid)
        resolution_png = _render_resolution_png(service, gid)
        assert resolution_png[:8] == _PNG_MAGIC
        assert len(resolution_png) > _NONTRIVIAL_PNG_BYTES


class TestResolutionMapAcrossPhases:
    """V4 task 3: resolution maps for retreat and adjustment phases.

    Rather than playing the full 34-unit standard opening for several turns
    hoping for an organic dislodgement, this drives a hand-built minimal
    ``GameState`` through ``GameService.restore_snapshot`` -- a real, public
    entry point (also used by the snapshot-restore feature) -- so the guaranteed
    dislodge/build scenario below is small enough to reason about by hand while
    still exercising the genuine ``GameService.process_turn`` -> engine
    adjudicator -> ``resolution_dict_to_viz`` -> renderer pipeline throughout.

    Layout: FRANCE (A BUR, A RUH) attacks GERMANY's A MUN with support from RUH
    (2 vs 1 -> dislodged, retreats to SIL). GERMANY's second unit (A BER) and
    FRANCE's single starting center (PAR) are only there so neither power is
    wiped out or hits a 0-center edge case; after MUN changes hands at the Fall
    recompute, GERMANY has 2 units but 1 center and must disband one in
    ``W1901A``.
    """

    def _setup(self, service: GameService) -> str:
        gid = _new_game(service)
        state = GameState(
            year=1901,
            season=Season.SPRING,
            phase_type=PhaseType.MOVEMENT,
            units=frozenset({
                Unit(UnitKind.ARMY, "FRANCE", Location("BUR")),
                Unit(UnitKind.ARMY, "FRANCE", Location("RUH")),
                Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
                Unit(UnitKind.ARMY, "GERMANY", Location("BER")),
            }),
            ownership={"PAR": "FRANCE", "MUN": "GERMANY", "BER": "GERMANY"},
        )
        service.restore_snapshot(gid, state_to_dict(state), phase_code="S1901M")
        return gid

    def test_retreat_and_adjustment_resolution_maps_render(self, service):
        gid = self._setup(service)

        # -- Spring movement: FRANCE dislodges GERMANY's A MUN. --------------
        service.submit_orders(gid, "FRANCE", ["A BUR - MUN", "A RUH S A BUR - MUN"])
        service.submit_orders(gid, "GERMANY", ["A MUN H", "A BER H"])
        out = service.process_turn(gid)
        assert out["phase"] == "S1901R"

        view = service.view(gid)
        dislodged = {d["unit"]["location"]: d for d in view["dislodged"]}
        assert "MUN" in dislodged
        assert "SIL" in dislodged["MUN"]["retreats"]

        # Sitting in the retreat phase, the resolution map shows the movement
        # that caused it (the dislodged unit's marker, per the pre-existing
        # dislodged-position logic in overlays.py).
        movement_resolution_png = _render_resolution_png(service, gid)
        assert movement_resolution_png[:8] == _PNG_MAGIC
        assert len(movement_resolution_png) > _NONTRIVIAL_PNG_BYTES

        # -- Retreat: GERMANY retreats MUN's unit to SIL. --------------------
        service.submit_orders(gid, "GERMANY", ["A MUN R SIL"])
        out = service.process_turn(gid)
        assert out["phase"] == "F1901M"

        # Now the last resolution is the retreat itself -- exercises the
        # "retreat" branch of resolution_dict_to_viz/_draw_retreat_order.
        retreat_resolution_png = _render_resolution_png(service, gid)
        assert retreat_resolution_png[:8] == _PNG_MAGIC
        assert len(retreat_resolution_png) > _NONTRIVIAL_PNG_BYTES

        view = service.view(gid)
        provinces = {u["location"] for u in view["units"] if u["power"] == "GERMANY"}
        assert provinces == {"SIL", "BER"}

        # -- Fall movement: both sides hold; MUN's ownership flips to FRANCE. -
        service.submit_orders(gid, "FRANCE", ["A MUN H", "A RUH H"])
        service.submit_orders(gid, "GERMANY", ["A SIL H", "A BER H"])
        out = service.process_turn(gid)
        assert out["phase"] == "W1901A"  # GERMANY: 2 units, 1 center -> must disband

        view = service.view(gid)
        assert view["ownership"]["MUN"] == "FRANCE"

        fall_resolution_png = _render_resolution_png(service, gid)
        assert fall_resolution_png[:8] == _PNG_MAGIC
        assert len(fall_resolution_png) > _NONTRIVIAL_PNG_BYTES

        # -- Adjustment: GERMANY disbands the extra unit. --------------------
        service.submit_orders(gid, "GERMANY", ["D A SIL"])
        out = service.process_turn(gid)
        assert out["phase"] == "S1902M"

        # Exercises the "destroy" branch of resolution_dict_to_viz for a real
        # adjustment-phase (Disband) result, not a hand-built Resolution.
        adjustment_resolution_png = _render_resolution_png(service, gid)
        assert adjustment_resolution_png[:8] == _PNG_MAGIC
        assert len(adjustment_resolution_png) > _NONTRIVIAL_PNG_BYTES

        view = service.view(gid)
        provinces = {u["location"] for u in view["units"] if u["power"] == "GERMANY"}
        assert provinces == {"BER"}
