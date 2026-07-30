"""Track I2: pending orders must not be drawn as adjudicated failures.

``render_board_png_orders`` stamps ``status = "pending"`` onto every order, because
that map is drawn *before* adjudication. Hold, support and convoy drawing all tested
``status == "success"`` and styled everything else as a failure, so the pending-orders
map -- the one a player opens to check what they just submitted -- drew every support
in failure red with a "support cut" X struck through it, every convoy red and dashed
as though disrupted, and no hold indicator at all.

Only movement (which spelled out ``or status == "pending"``) and retreat (which tested
``== "failed"``) were correct. Two of six paths looking right is why this survived.
"""
from __future__ import annotations

import pytest
from PIL import ImageColor

from rendering import overlays
from rendering.overlays import _drawn_as_ok
from rendering.visualization_config import get_config

pytestmark = pytest.mark.map

COORDS = {
    "PIC": (523.5, 781.0),
    "BEL": (561.5, 753.0),
    "YOR": (492.5, 616.0),
    "NTH": (520.0, 500.0),
    "HOL": (600.0, 700.0),
}


class _Spy:
    """Records every draw call as (method, kwargs)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, name: str):
        def record(*args, **kwargs):
            self.calls.append((name, kwargs))

        return record

    def colours(self) -> set[tuple[int, int, int]]:
        """Every colour used, normalized to RGB.

        Normalizing matters: the drawing primitives are inconsistent about whether
        they hand PIL a name (``"red"``), a hex string (``"#FF0000"``) or an RGB
        tuple, and an assertion that checks only one form passes vacuously against
        the other two. Verified: a failed convoy emits ``'#FF0000'`` as a fill and
        ``(255, 0, 0)`` as an outline in the same call sequence.
        """
        out = set()
        for _, kw in self.calls:
            for key in ("fill", "outline"):
                value = kw.get(key)
                if value is not None:
                    out.add(_rgb(value))
        return out


def _rgb(colour) -> tuple[int, int, int]:
    """Resolve any colour the primitives use to an RGB triple.

    Uses PIL's own resolver rather than ``rendering.board._convert_color_to_rgb``,
    which passes CSS colour *names* straight through for PIL to handle -- so it
    returns the string ``"red"`` unchanged, and ``tuple("red")`` is ``('r','e','d')``.
    """
    if isinstance(colour, str):
        return ImageColor.getrgb(colour)[:3]
    return tuple(colour)[:3]


def _failure_rgb() -> tuple[int, int, int]:
    return _rgb(get_config().get_color("failure"))


class TestDrawnAsOk:
    @pytest.mark.parametrize("status", ["success", "pending"])
    def test_not_a_failure(self, status):
        assert _drawn_as_ok(status) is True

    @pytest.mark.parametrize("status", ["failed", "bounced", "dislodged"])
    def test_real_failures(self, status):
        """The full status vocabulary from order_overlay._STATUS_BY_CODE."""
        assert _drawn_as_ok(status) is False

    def test_unknown_status_is_treated_as_a_failure(self):
        """Fail loud-ish: a status the renderer does not know should not silently
        acquire the success styling."""
        assert _drawn_as_ok("who-knows") is False


class TestSupportStyling:
    def test_pending_hold_support_draws_no_cut_indicator(self):
        """The bug: a red X struck through every support before adjudication."""
        calls: list = []
        original = overlays._draw_support_cut_indicator
        overlays._draw_support_cut_indicator = lambda *a, **k: calls.append(a)
        try:
            overlays._draw_support_order(
                _Spy(), "PIC", "BEL", "hold", None, "royalblue", "pending", COORDS
            )
        finally:
            overlays._draw_support_cut_indicator = original
        assert calls == []

    def test_failed_hold_support_still_draws_the_cut_indicator(self):
        """The fix must not simply disable the indicator."""
        calls: list = []
        original = overlays._draw_support_cut_indicator
        overlays._draw_support_cut_indicator = lambda *a, **k: calls.append(a)
        try:
            overlays._draw_support_order(
                _Spy(), "PIC", "BEL", "hold", None, "royalblue", "failed", COORDS
            )
        finally:
            overlays._draw_support_cut_indicator = original
        assert len(calls) == 1

    def test_pending_hold_support_circles_the_supported_unit(self):
        """The circle marks "this unit is being supported" and was omitted entirely."""
        spy = _Spy()
        overlays._draw_support_order(
            spy, "PIC", "BEL", "hold", None, "royalblue", "pending", COORDS
        )
        assert any(name == "ellipse" for name, _ in spy.calls)

    def test_pending_support_is_not_drawn_in_failure_red(self):
        spy = _Spy()
        overlays._draw_support_order(
            spy, "PIC", "BEL", "hold", None, "royalblue", "pending", COORDS
        )
        assert _failure_rgb() not in spy.colours()

    def test_failed_support_is_drawn_in_failure_red(self):
        spy = _Spy()
        overlays._draw_support_order(
            spy, "PIC", "BEL", "hold", None, "royalblue", "failed", COORDS
        )
        assert _failure_rgb() in spy.colours()

    def test_pending_move_support_draws_no_cut_indicator(self):
        calls: list = []
        original = overlays._draw_support_cut_indicator
        overlays._draw_support_cut_indicator = lambda *a, **k: calls.append(a)
        try:
            overlays._draw_support_order(
                _Spy(), "PIC", "YOR", "move", "BEL", "royalblue", "pending", COORDS
            )
        finally:
            overlays._draw_support_cut_indicator = original
        assert calls == []


class TestConvoyStyling:
    def test_pending_convoy_is_not_drawn_in_failure_red(self):
        """A pending convoy was drawn red and dashed, i.e. as a disrupted one."""
        spy = _Spy()
        overlays._draw_convoy_order(
            spy, "YOR", "BEL", ["NTH"], get_config().get_color("convoy"), "pending", COORDS
        )
        assert _failure_rgb() not in spy.colours()
        assert _rgb(get_config().get_color("convoy")) in spy.colours()

    def test_failed_convoy_is_drawn_in_failure_red(self):
        spy = _Spy()
        overlays._draw_convoy_order(
            spy, "YOR", "BEL", ["NTH"], get_config().get_color("convoy"), "failed", COORDS
        )
        assert _failure_rgb() in spy.colours()


class TestHoldStyling:
    def test_pending_hold_draws_an_indicator_in_the_power_colour(self):
        """A pending hold drew nothing at all -- so on the orders map, submitting a
        hold looked identical to submitting nothing."""
        spy = _Spy()
        overlays._draw_hold_order(spy, "BEL", "royalblue", "pending", COORDS)
        assert spy.calls, "a pending hold must still be visible"
        assert _rgb("royalblue") in spy.colours()
        assert _failure_rgb() not in spy.colours()

    def test_failed_hold_is_still_marked_red(self):
        spy = _Spy()
        overlays._draw_hold_order(spy, "BEL", "royalblue", "failed", COORDS)
        assert _failure_rgb() in spy.colours()


class TestOrdersMapEndToEnd:
    """The whole point: a real render of an all-pending orders map must contain no
    failure indicators at all."""

    def test_orders_map_never_draws_a_support_cut(self, tmp_path):
        cuts: list = []
        original = overlays._draw_support_cut_indicator
        overlays._draw_support_cut_indicator = lambda *a, **k: cuts.append(a)
        try:
            from rendering.map import Map

            units = {
                "ENGLAND": ["A YOR", "F NTH"],
                "FRANCE": ["A BEL", "A PIC"],
            }
            orders = {
                "ENGLAND": [
                    {"type": "convoy", "unit": "F NTH", "convoyed_army_province": "YOR",
                     "target": "BEL", "via": ["NTH"], "status": "success"},
                    {"type": "move", "unit": "A YOR", "target": "BEL", "status": "success"},
                ],
                "FRANCE": [
                    {"type": "support", "unit": "A PIC", "supporting": "A BEL",
                     "supported_unit_province": "BEL", "status": "success"},
                    {"type": "hold", "unit": "A BEL", "status": "success"},
                ],
            }
            png = Map.render_board_png_orders(
                svg_path="maps/standard.svg",
                units=units,
                orders=orders,
                phase_info={"phase_code": "S1902M", "season": "Spring",
                            "phase": "Movement", "turn": 2},
                output_path=str(tmp_path / "orders.png"),
            )
            assert png.startswith(b"\x89PNG\r\n\x1a\n")
        finally:
            overlays._draw_support_cut_indicator = original
        assert cuts == [], "no order has been adjudicated, so nothing can be cut"
