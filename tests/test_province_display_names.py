"""Province display names reach clients without contaminating the wire format (G2).

`MapData` exposed `provinces`, `aliases`, … and **no display-name map**, so every
surface showed 3-letter codes: the web board, the roster, the order lists, the
resolution panel, and the bot's inline keyboards. The full names were being read
all along — they are the left-hand side of `maps/standard.map`'s `=` lines
(`Adriatic Sea = adr adriatic`) — and simply discarded by the parser.

The constraint that makes this delicate: **codes remain the wire format.** G1
established that the engine will not accept full province names (26 are multi-word
and `parser._tokenize` splits on whitespace), so a name substituted into an order
string produces `unknown province`. These tests pin the display/wire split.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.map_loader import load_standard_map
from engine.orders.parser import OrderParseError, parse_order


@pytest.mark.unit
def test_every_province_has_a_display_name() -> None:
    """A partial table is worse than none: the UI would look inconsistent."""
    map_data = load_standard_map()
    missing = sorted(p for p in map_data.provinces if p not in map_data.display_names)
    assert not missing, f"provinces with no display name: {missing}"
    extra = sorted(k for k in map_data.display_names if k not in map_data.provinces)
    assert not extra, f"display names for non-provinces: {extra}"


@pytest.mark.unit
def test_display_names_are_the_human_readable_left_hand_side() -> None:
    map_data = load_standard_map()
    assert map_data.display_names["BER"] == "Berlin"
    assert map_data.display_names["NTH"] == "North Sea"
    assert map_data.display_names["ENG"] == "English Channel"
    assert map_data.display_names["MAO"] == "Mid-Atlantic Ocean"
    assert map_data.display_names["TYR"] == "Tyrolia"


@pytest.mark.unit
def test_split_coast_provinces_get_the_bare_name_not_a_coast_qualified_one() -> None:
    """The subtle bug this guards.

    Split-coast provinces have *three* `=` lines each — "Bulgaria (east coast)",
    "Bulgaria (south coast)", "Bulgaria" — and all three resolve to the same
    canonical code `BUL`. Taking whichever came first would make the UI render a
    plain `BUL` unit as "Bulgaria (east coast)", which is actively wrong.
    """
    names = load_standard_map().display_names
    assert names["BUL"] == "Bulgaria"
    assert names["SPA"] == "Spain"
    assert names["STP"] == "St Petersburg"
    for code, name in names.items():
        assert "coast" not in name.lower(), f"{code} kept a coast-qualified name: {name!r}"


@pytest.mark.unit
def test_display_names_are_not_registered_as_parseable_aliases() -> None:
    """G2 must not accidentally implement the thing G1 decided against.

    Adding names to `aliases` would make `A Berlin - Kiel` parse for single-word
    provinces while `F English Channel - NTH` still failed — the inconsistent
    half-support G1 rejected. `display_names` is a separate field for that reason.
    """
    map_data = load_standard_map()
    assert map_data.aliases.get("berlin") is None
    with pytest.raises(OrderParseError):
        parse_order("A Berlin - Kiel", power="GERMANY", map=map_data)
    # And the canonical form still works, unchanged.
    assert parse_order("A BER - KIE", power="GERMANY", map=map_data)


@pytest.mark.unit
def test_engine_stays_stdlib_only() -> None:
    """`display_names` is plain data; it must not have pulled I/O into the engine."""
    import engine.map_loader as ml

    source = open(ml.__file__, encoding="utf-8").read()
    for forbidden in ("import requests", "import sqlalchemy", "from fastapi", "import fastapi"):
        assert forbidden not in source, f"engine gained a non-stdlib dependency: {forbidden}"


@pytest.mark.unit
def test_provinces_endpoint_serves_the_names() -> None:
    from server.api import app

    client = TestClient(app)
    resp = client.get("/maps/standard/provinces")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["map_name"] == "standard"
    provinces = body["provinces"]

    map_data = load_standard_map()
    assert set(provinces) == set(map_data.provinces)
    assert provinces["BER"]["name"] == "Berlin"
    assert provinces["BER"]["is_supply_center"] is True
    assert provinces["NTH"]["type"] == "WATER"
    assert provinces["NTH"]["is_supply_center"] is False
    # Coasts are reported so a client can render `STP/SC` sensibly.
    assert provinces["STP"]["coasts"] == ["NC", "SC"]
    assert provinces["BER"]["coasts"] == []


@pytest.mark.unit
def test_provinces_endpoint_404s_on_an_unknown_map() -> None:
    from server.api import app

    assert TestClient(app).get("/maps/nope/provinces").status_code == 404


# --- the bot's label helper -------------------------------------------------


@pytest.mark.unit
def test_bot_location_label_shows_name_and_code() -> None:
    """The code has to stay visible: a player types codes, not names."""
    from server.telegram_bot import orders as bot_orders

    bot_orders._reset_province_names_cache()
    try:
        bot_orders._PROVINCE_NAMES.update({"BER": "Berlin", "STP": "St Petersburg"})
        bot_orders._PROVINCE_NAMES_FETCHED = True
        assert bot_orders._location_label("BER") == "Berlin (BER)"
        # A coast qualifier belongs to the code half, not the name.
        assert bot_orders._location_label("STP/SC") == "St Petersburg (STP/SC)"
    finally:
        bot_orders._reset_province_names_cache()


@pytest.mark.unit
def test_bot_location_label_falls_back_to_the_code() -> None:
    """The table is fetched lazily and best-effort, so this path is normal."""
    from unittest.mock import patch

    from server.telegram_bot import orders as bot_orders

    bot_orders._reset_province_names_cache()
    try:
        with patch("server.telegram_bot.orders.api_get", side_effect=OSError("api down")):
            assert bot_orders._location_label("BER") == "BER"
    finally:
        bot_orders._reset_province_names_cache()


@pytest.mark.unit
def test_bot_fetches_province_names_at_most_once() -> None:
    """A per-button HTTP call would be a real cost; a missing name is cosmetic."""
    from unittest.mock import patch

    from server.telegram_bot import orders as bot_orders

    bot_orders._reset_province_names_cache()
    try:
        payload = {"provinces": {"BER": {"name": "Berlin"}}}
        with patch("server.telegram_bot.orders.api_get", return_value=payload) as mock_get:
            for _ in range(5):
                bot_orders._location_label("BER")
        assert mock_get.call_count == 1, mock_get.call_count
    finally:
        bot_orders._reset_province_names_cache()


@pytest.mark.unit
def test_bot_order_labels_stay_in_codes() -> None:
    """Full order strings must not gain names — Telegram truncates at 60 chars.

    `A MAR S A PAR - BUR` fits; "Army Marseilles supports Army Paris → Burgundy"
    does not, and a truncated order label is worse than a terse one.
    """
    from server.telegram_bot import orders as bot_orders

    bot_orders._reset_province_names_cache()
    try:
        bot_orders._PROVINCE_NAMES.update({"MAR": "Marseilles", "PAR": "Paris", "BUR": "Burgundy"})
        bot_orders._PROVINCE_NAMES_FETCHED = True
        label = bot_orders._order_label("A MAR S A PAR - BUR")
        assert "A MAR S A PAR - BUR" in label
        assert "Marseilles" not in label
        assert len(label) <= 60
    finally:
        bot_orders._reset_province_names_cache()
