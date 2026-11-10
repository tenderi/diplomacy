"""Track DC1: retreat-phase bot fixes (a disband counts as an order; forced disbands are not walked)."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from server.telegram_bot import hub
from server.telegram_bot import orders as bot_orders
from tests.test_order_all_flow import Chat, api  # noqa: F401  (api is a fixture)

pytestmark = pytest.mark.unit

FORCED = {
    "phase": "S1901R", "phase_type": "RETREAT",
    "units": [{"kind": "A", "location": "WAR"}],
    "orders": ["D A WAR"],
    "orders_by_unit": {"A WAR": ["D A WAR"]},
}
MIXED = {
    "phase": "S1901R", "phase_type": "RETREAT",
    "units": [{"kind": "A", "location": "MUN"}, {"kind": "A", "location": "WAR"}],
    "orders": ["A MUN R BOH", "D A MUN", "D A WAR"],
    "orders_by_unit": {"A MUN": ["A MUN R BOH", "D A MUN"], "A WAR": ["D A WAR"]},
}
FORCED_TEXT = "A WAR has nowhere to retreat and is disbanded automatically."


@pytest.mark.parametrize(
    "order,key,expected",
    [
        ("D A MUN", "A MUN", True),
        ("A MUN D", "A MUN", True),
        ("DISBAND A MUN", "A MUN", True),
        ("A MUN R BOH", "A MUN", True),
        ("D F SPA/SC", "F SPA/SC", True),
        ("F SPA R POR", "F SPA/SC", True),
        ("D A MUNICH", "A MUN", False),
        ("A PAR S A MUN", "A MUN", False),
        ("D F MUN", "A MUN", False),
    ],
)
def test_order_is_for_unit(order: str, key: str, expected: bool) -> None:
    assert bot_orders.order_is_for_unit(order, key) is expected


@pytest.mark.parametrize("pending", [["D A MUN"], ["A MUN D"]])
def test_disband_is_not_reported_as_unordered(pending: list[str]) -> None:
    legal = {**MIXED, "units": MIXED["units"][:1]}

    def get(path: str, **_kw: Any) -> Any:
        return {"orders": pending} if "/orders/" in path else legal

    with patch.object(bot_orders, "api_get", side_effect=get):
        assert bot_orders.unordered_note("1", "GERMANY", "5") == ""


def test_walk_skips_a_unit_that_can_only_disband(api) -> None:  # noqa: F811
    api.get.side_effect = lambda path, **_kw: {"phase": "S1901R"} if path.endswith("/state") else FORCED
    chat = Chat()
    chat.command([])
    assert chat.text == "✅ " + FORCED_TEXT
    assert not chat.buttons


def test_walk_only_walks_units_with_a_retreat(api) -> None:  # noqa: F811
    api.get.side_effect = lambda path, **_kw: {"phase": "S1901R"} if path.endswith("/state") else MIXED
    chat = Chat()
    chat.command([])
    assert "Unit 1/1" in chat.text and "A MUN" in chat.text


def test_hub_treats_a_forced_disband_power_as_having_nothing_to_order() -> None:
    sent: list[str] = []

    async def send(text: str, reply_markup: Any = None, **_kw: Any) -> None:
        sent.append(text)

    def get(path: str, **_kw: Any) -> Any:
        if path.endswith("/state"):
            return {"phase_type": "RETREAT", "status": "ACTIVE"}
        return FORCED

    with patch.object(hub, "resolve_game_and_power", return_value=("7", "RUSSIA")), \
         patch.object(hub, "fetch_user_games", return_value=[]), \
         patch.object(hub, "status_text", return_value="HDR"), \
         patch.object(hub, "api_get", side_effect=get):
        asyncio.run(hub.show_hub(send, "5", "7"))
    assert sent == ["HDR\n" + FORCED_TEXT]
    markup: Any = hub._hub_keyboard("7", "RUSSIA", {"status": "ACTIVE"}, None, False, FORCED)
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert "📝 Order all units" not in labels


def test_unit_picker_skips_a_forced_disband() -> None:
    sent: list[str] = []

    async def reply(text: str, reply_markup: Any = None, **_kw: Any) -> None:
        sent.append(text)

    with patch.object(bot_orders, "resolve_game_and_power", return_value=("7", "RUSSIA")), \
         patch.object(bot_orders, "api_get", return_value=FORCED):
        asyncio.run(bot_orders.show_unit_picker(reply, Chat().context, "5", "7"))
    assert sent == [FORCED_TEXT]


# -- DC2/DC3: readable retreat buttons and retreat context ---------------------------

SPAIN = {
    "phase": "S1901R", "phase_type": "RETREAT",
    "units": [{"kind": "F", "location": "SPA/SC"}],
    "orders": ["D F SPA/SC", "F SPA/SC R MAO", "F SPA/SC R MAR"],
    "orders_by_unit": {"F SPA/SC": ["D F SPA/SC", "F SPA/SC R MAO", "F SPA/SC R MAR"]},
}
CONTEXT = "Your F SPA/SC was dislodged: retreat to MAO or MAR, or disband. With no order it is disbanded."


NAMES = {"MAO": "Mid-Atlantic Ocean", "MAR": "Marseilles", "BOH": "Bohemia", "BOT": "Gulf of Bothnia"}


def test_retreat_label_spells_out_the_target_and_stays_in_the_button_width(monkeypatch) -> None:
    monkeypatch.setattr(bot_orders, "province_names", lambda: NAMES)
    assert bot_orders._order_label("F SPA/SC R MAO") == "↩️ Retreat to Mid-Atlantic Ocean (MAO)"
    assert bot_orders._order_label("A MUN R BOH") == "↩️ Retreat to Bohemia (BOH)"
    assert bot_orders._order_label("F STP/SC R BOT") == "↩️ Retreat to Gulf of Bothnia (BOT)"
    assert len(bot_orders._order_label("F SPA/SC R MAO")) <= 60


def test_walk_step_lists_retreats_before_the_disband_and_gives_context(api, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(bot_orders, "province_names", lambda: NAMES)
    api.get.side_effect = lambda path, **_kw: {"phase": "S1901R"} if path.endswith("/state") else SPAIN
    chat = Chat()
    chat.command([])
    labels = [t for t, d in chat.buttons if d.startswith("ord|")]
    assert labels[0] == "↩️ Retreat to Mid-Atlantic Ocean (MAO)"
    assert labels[1].startswith("↩️ Retreat to Marseilles")
    assert labels[2].startswith("✂️ Disband")
    assert CONTEXT in chat.text
    cached = list(chat.context.user_data["pending_orders"].values())
    assert cached == [["F SPA/SC R MAO", "F SPA/SC R MAR", "D F SPA/SC"]]


def test_unit_picker_gives_the_retreat_context() -> None:
    sent: list[str] = []

    async def reply(text: str, reply_markup: Any = None, **_kw: Any) -> None:
        sent.append(text)

    with patch.object(bot_orders, "resolve_game_and_power", return_value=("7", "SPAIN")), \
         patch.object(bot_orders, "api_get", return_value=SPAIN):
        asyncio.run(bot_orders.show_unit_picker(reply, Chat().context, "5", "7"))
    assert CONTEXT in sent[0]


def test_hub_shows_the_retreat_duty_and_the_forced_disband() -> None:
    assert bot_orders.retreat_duty(SPAIN) == CONTEXT
    assert bot_orders.retreat_duty(MIXED) == (
        "Your A MUN was dislodged: retreat to BOH, or disband. With no order it is disbanded.\n" + FORCED_TEXT
    )
    assert bot_orders.retreat_duty({**FORCED, "units": []}) == ""
    sent: list[str] = []

    async def send(text: str, reply_markup: Any = None, **_kw: Any) -> None:
        sent.append(text)

    def get(path: str, **_kw: Any) -> Any:
        return {"phase_type": "RETREAT", "status": "ACTIVE"} if path.endswith("/state") else SPAIN

    with patch.object(hub, "resolve_game_and_power", return_value=("7", "SPAIN")), \
         patch.object(hub, "fetch_user_games", return_value=[]), \
         patch.object(hub, "status_text", return_value="HDR"), \
         patch.object(hub, "api_get", side_effect=get):
        asyncio.run(hub.show_hub(send, "5", "7"))
    assert sent == ["HDR\n" + CONTEXT]
