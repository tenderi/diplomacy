"""What a turn looks like: each order and outcome drawn where it belongs.

Orders are adjudicated by the real engine (``GameService.sandbox_adjudicate``) and
planned by ``rendering.overlays.plan_orders``; a spy records every drawing call of
each planned operation, in board coordinates, so the assertions are about *where*
and *how* things are drawn -- which the PNG bytes alone cannot show.

The defects this guards against were all real: a bounce's ✗ drawn on the defender
that held, a won head-to-head's ✓ on the loser, the winner wearing the loser's
dislodged ring, supports with arrowheads, holds hidden under the unit icon.
"""
from __future__ import annotations

import math
from typing import Any

import pytest
from PIL import ImageColor

from rendering.board import get_dislodged_unit_coordinates, get_svg_province_coordinates
from rendering.order_overlay import orders_by_power_to_viz, resolution_dict_to_viz, standoff_provinces
from rendering.overlays import Plan, build_scene, plan_orders
from rendering.tokens import token_radius
from rendering.view_adapter import units_for_render
from rendering.visualization_config import get_config
from server.game_service import GameService

pytestmark = pytest.mark.unit

SVG = "maps/standard.svg"
CENTRES = get_svg_province_coordinates(SVG)
_cfg = get_config()
FAILURE = ImageColor.getrgb(_cfg.get_color("failure"))
VOID = ImageColor.getrgb(_cfg.get_color("void"))


class Spy:
    """Records every drawing call; coordinates are already in board space."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict]] = []

    def __getattr__(self, name: str):
        return lambda xy=None, *a, **k: self.calls.append((name, xy, k))

    def points(self) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for _, xy, _ in self.calls:
            flat = list(_flatten(xy))
            out += list(zip(flat[0::2], flat[1::2]))
        return out

    def ellipse_centres(self) -> list[tuple[float, float]]:
        return [((xy[0] + xy[2]) / 2, (xy[1] + xy[3]) / 2) for name, xy, _ in self.calls if name == "ellipse"]

    def colours(self) -> set[tuple[int, ...]]:
        found = set()
        for _, _, k in self.calls:
            for key in ("fill", "outline"):
                c = k.get(key)
                if c is not None:
                    found.add(tuple(ImageColor.getrgb(c) if isinstance(c, str) else c)[:3])
        return found


def _flatten(xy: Any):
    if isinstance(xy, (int, float)):
        yield float(xy)
    elif isinstance(xy, (list, tuple)):
        for item in xy:
            yield from _flatten(item)


def _run(ops) -> list[Spy]:
    spies = []
    for op in ops:
        spy = Spy()
        op(spy)
        spies.append(spy)
    return spies


def _board(units: dict[str, list[str]]) -> tuple[GameService, Any]:
    gs = GameService(None)
    s = gs.sandbox_opening()
    s["units"] = [{"kind": u[0], "power": p, "location": u[2:]} for p, us in units.items() for u in us]
    s["ownership"] = {}
    return gs, gs.sandbox_state(s)


def _turn(units: dict[str, list[str]], orders: dict[str, list[str]]) -> tuple[Plan, dict]:
    """Adjudicate ``orders`` and plan their picture on the board they were given on."""
    gs, state = _board(units)
    view = gs.sandbox_view(state)
    res = gs.sandbox_adjudicate(state, orders)["resolution"]
    kinds = {u["location"]: u["kind"] for u in view["units"]}
    scene = build_scene(units_for_render(view), SVG)
    return plan_orders(resolution_dict_to_viz(res, kinds), scene, standoff_provinces(res)), res


def _near(point: tuple[float, float], province: str, radius: float) -> bool:
    return math.dist(point, CENTRES[province]) <= radius


def _markers_near(plan: Plan, province: str, radius: float) -> list[Spy]:
    return [s for s in _run(plan.over) if any(_near(p, province, radius) for p in s.points())]


class TestBounces:
    def test_a_bounce_stops_at_the_border_and_marks_nothing_on_the_defender(self) -> None:
        plan, res = _turn({"RUSSIA": ["A PRU"], "GERMANY": ["A BER"]},
                          {"RUSSIA": ["A PRU - BER"], "GERMANY": ["A BER H"]})
        assert [r["result"] for r in res["results"] if r["order"]["type"] == "MOVE"] == ["BOUNCE"]
        bars = [s for s in _run(plan.over) if FAILURE in s.colours()]
        assert len(bars) == 1
        (a, b) = [p for p in bars[0].points()][-2:]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        border = ((CENTRES["PRU"][0] + CENTRES["BER"][0]) / 2, (CENTRES["PRU"][1] + CENTRES["BER"][1]) / 2)
        assert math.dist(mid, border) < 3
        # The defender held: nothing red anywhere on it.
        assert not [s for s in _markers_near(plan, "BER", token_radius()) if FAILURE in s.colours()]
        assert "bounce" in plan.legend and "failed" not in plan.legend

    def test_a_standoff_is_marked_in_the_empty_province(self) -> None:
        plan, _ = _turn({"ITALY": ["A VEN"], "AUSTRIA": ["A VIE"]},
                        {"ITALY": ["A VEN - TYR"], "AUSTRIA": ["A VIE - TYR"]})
        burst = [s for s in _run(plan.over) if ImageColor.getrgb(_cfg.get_color("standoff")) in s.colours()]
        assert len(burst) == 1
        xs, ys = zip(*burst[0].points())
        assert math.dist((sum(xs) / len(xs), sum(ys) / len(ys)), CENTRES["TYR"]) < 1
        assert {"bounce", "standoff"} <= plan.legend

    def test_a_standoff_beside_a_unit_that_left_does_not_cover_it(self) -> None:
        """BUR's own army moves out while two others bounce there: the burst goes to
        BUR's free spot, not over the army that left."""
        plan, _ = _turn({"GERMANY": ["A BUR"], "FRANCE": ["A PAR", "A MAR"]},
                        {"GERMANY": ["A BUR - BEL"], "FRANCE": ["A PAR - BUR", "A MAR - BUR"]})
        burst = [s for s in _run(plan.over) if ImageColor.getrgb(_cfg.get_color("standoff")) in s.colours()]
        xs, ys = zip(*burst[0].points())
        assert math.dist((sum(xs) / len(xs), sum(ys) / len(ys)), get_dislodged_unit_coordinates(SVG)["BUR"]) < 1


class TestDislodgement:
    def test_a_won_head_to_head_rings_the_loser_not_the_winner(self) -> None:
        plan, res = _turn({"FRANCE": ["A PAR", "A PIC"], "GERMANY": ["A BUR"]},
                          {"FRANCE": ["A PAR - BUR", "A PIC S A PAR - BUR"], "GERMANY": ["A BUR - PAR"]})
        assert {(r["order"]["unit"], r["result"], r["dislodged"]) for r in res["results"]} >= {
            ("PAR", "OK", False), ("BUR", "BOUNCE", True)}
        ringed = [s for s in _run(plan.over) if FAILURE in s.colours() and s.ellipse_centres()]
        assert len(ringed) == 1 and all(_near(c, "BUR", 0.5) for c in ringed[0].ellipse_centres())
        assert not _markers_near(plan, "PAR", token_radius())
        assert "dislodged" in plan.legend

    def test_a_dislodged_supporter_is_ringed(self) -> None:
        plan, res = _turn({"AUSTRIA": ["A BOH", "A TYR"], "GERMANY": ["A MUN", "A KIE"]},
                          {"AUSTRIA": ["A BOH - MUN", "A TYR S A BOH - MUN"], "GERMANY": ["A MUN S A KIE - RUH", "A KIE - RUH"]})
        mun = next(r for r in res["results"] if r["order"]["unit"] == "MUN")
        assert (mun["result"], mun["dislodged"]) == ("CUT", True)
        ringed = [s for s in _run(plan.over) if FAILURE in s.colours() and s.ellipse_centres()]
        assert [c for s in ringed for c in s.ellipse_centres() if not _near(c, "MUN", 0.5)] == []
        assert ringed


class TestMoves:
    def test_a_move_reaches_an_empty_province_and_stops_short_of_a_unit(self) -> None:
        plan, _ = _turn({"FRANCE": ["A PAR"], "GERMANY": ["A MUN", "A KIE"]},
                        {"FRANCE": ["A PAR - GAS"], "GERMANY": ["A MUN H", "A KIE - BER"]})
        tips = [s.calls[-1][1][0] for s in _run(plan.under) if s.calls and s.calls[-1][0] == "polygon"]
        assert any(math.dist(t, CENTRES["GAS"]) < 6 for t in tips)
        assert any(math.dist(t, CENTRES["BER"]) < 6 for t in tips)

    def test_opposed_moves_are_drawn_side_by_side(self) -> None:
        plan, _ = _turn({"ENGLAND": ["A BEL"], "GERMANY": ["A RUH"]},
                        {"ENGLAND": ["A BEL - RUH"], "GERMANY": ["A RUH - BEL"]})
        lines = [s for s in _run(plan.under) if s.calls]
        assert len(lines) == 2
        a, b = CENTRES["BEL"], CENTRES["RUH"]

        def side(p: tuple[float, float]) -> float:  # signed distance from the BEL-RUH line
            return ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / math.dist(a, b)

        sides = sorted(side(s.points()[0]) for s in lines)
        want = _cfg.get_arrow_specs()["opposed_offset"]
        assert sides == pytest.approx([-want, want], abs=0.5)

    def test_a_convoyed_move_runs_through_its_fleet(self) -> None:
        plan, _ = _turn({"ENGLAND": ["A LON", "F NTH"]},
                        {"ENGLAND": ["A LON - NWY VIA", "F NTH C A LON - NWY"]})
        assert any(_near(p, "NTH", 2) for s in _run(plan.under) for p in s.points())
        assert "convoy" in plan.legend and "move" not in plan.legend


class TestSupportsAndHolds:
    def test_supports_have_no_arrowhead(self) -> None:
        plan, _ = _turn({"FRANCE": ["A PAR", "A MAR"], "GERMANY": ["A MUN", "A BUR"]},
                        {"FRANCE": ["A PAR - GAS", "A MAR S A PAR - GAS"], "GERMANY": ["A MUN S A BUR", "A BUR H"]})
        mar = CENTRES["MAR"]
        support_ops = [s for s in _run(plan.under) if s.calls and math.dist(s.points()[0], mar) < token_radius() + 8]
        assert support_ops and not any(name == "polygon" for s in support_ops for name, _, _ in s.calls)

    def test_support_to_move_ends_on_the_supported_arrow(self) -> None:
        plan, _ = _turn({"FRANCE": ["A PAR", "A MAR"]}, {"FRANCE": ["A PAR - BUR", "A MAR S A PAR - BUR"]})
        dots = [s for s in _run(plan.under) if [c[0] for c in s.calls] == ["ellipse", "ellipse"]]
        assert len(dots) == 1
        x0, y0, x1, y1 = dots[0].calls[1][1]
        centre = ((x0 + x1) / 2, (y0 + y1) / 2)
        a, b = CENTRES["PAR"], CENTRES["BUR"]
        # perpendicular distance from the PAR→BUR line
        dist = abs((b[0] - a[0]) * (a[1] - centre[1]) - (a[0] - centre[0]) * (b[1] - a[1])) / math.dist(a, b)
        assert dist < 1

    def test_cut_and_void_supports_look_different(self) -> None:
        cut, res = _turn({"FRANCE": ["A BUR", "A PAR"], "GERMANY": ["A MUN"]},
                         {"FRANCE": ["A BUR S A PAR", "A PAR H"], "GERMANY": ["A MUN - BUR"]})
        void, _ = _turn({"FRANCE": ["A BUR", "A PAR"]}, {"FRANCE": ["A BUR S A PAR", "A PAR - PIC"]})
        assert next(r["result"] for r in res["results"] if r["order"]["unit"] == "BUR") == "CUT"
        assert "cut" in cut.legend and "void" not in cut.legend
        assert "void" in void.legend and "cut" not in void.legend
        assert any(FAILURE in s.colours() for s in _run(cut.over))
        assert any(VOID in s.colours() for s in _run(void.under))
        assert not any(FAILURE in s.colours() for s in _run(void.over))

    def test_a_hold_is_drawn_outside_the_unit(self) -> None:
        plan, _ = _turn({"GERMANY": ["A BER"]}, {"GERMANY": ["A BER H"]})
        (spy,) = _run(plan.over)
        assert min(math.dist(p, CENTRES["BER"]) for p in spy.points()) > token_radius()


def test_the_orders_map_shows_no_outcomes() -> None:
    """Before adjudication nothing has failed: no red, no grey, no bars."""
    gs, state = _board({"FRANCE": ["A PAR", "A MAR"], "GERMANY": ["A MUN", "A BUR"]})
    view = gs.sandbox_view(state)
    _, parsed = gs.sandbox_orders(state, {"FRANCE": ["A PAR - BUR", "A MAR S A PAR - BUR"],
                                          "GERMANY": ["A MUN S A BUR", "A BUR H"]})
    plan = plan_orders(orders_by_power_to_viz(parsed), build_scene(units_for_render(view), SVG))
    colours = set().union(*(s.colours() for s in _run(plan.under) + _run(plan.over)))
    assert FAILURE not in colours and VOID not in colours
    assert plan.legend == {"move", "hold", "support_move", "support_hold"}


def test_a_retreat_starts_from_the_dislodged_unit() -> None:
    gs, state = _board({"FRANCE": ["A PAR", "A MAR"], "GERMANY": ["A BUR"]})
    after = gs.sandbox_adjudicate(state, {"FRANCE": ["A PAR - BUR", "A MAR S A PAR - BUR"]})
    retreat_state = gs.sandbox_state(after["state"])
    view = after["view"]
    _, parsed = gs.sandbox_orders(retreat_state, {"GERMANY": ["A BUR R PIC"]})
    plan = plan_orders(orders_by_power_to_viz(parsed), build_scene(units_for_render(view), SVG))
    (spy,) = [s for s in _run(plan.under) if s.calls]
    start = spy.points()[0]
    anchor = get_dislodged_unit_coordinates(SVG)["BUR"]
    assert math.dist(start, anchor) < token_radius() + 8 < math.dist(start, CENTRES["BUR"])
