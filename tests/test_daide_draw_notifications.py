"""A draw voted over DAIDE notifies the Telegram players (BD8).

`DaideSession._cmd_drw` used to call `GameService.submit_draw_vote` directly, so a
DAIDE vote, its withdrawal (`NOT (DRW)`) and a draw it completed reached only the
DAIDE sessions. Both surfaces now run `api.shared.after_draw_vote`: the HTTP route
directly, the DAIDE listener through the `on_draw_vote` hook `_api_module` gives it.
These tests seat seven Telegram players over HTTP and let one power vote over DAIDE.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.daide import tokens as t
from server.daide.server import DaideServer
from server.daide.session import DaideSession
from server.daide.tokens import Token
from tests.reliability_helpers import OutboxProbe
from tests.test_draw_concede_notifications import GROUP, POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


class _Writer:
    """Captures every DCSP frame a session writes, without a socket."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    def frames(self) -> list[list[Token]]:
        return [[Token.from_bytes(f[4:][i : i + 2]) for i in range(0, len(f) - 4, 2)] for f in self.sent]


def _daide_seat(game_id: str, power: str) -> tuple[DaideSession, _Writer]:
    """A DAIDE session holding ``power`` in ``game_id``, on a listener wired the
    way `_api_module`'s lifespan wires the real one."""
    server = DaideServer(api_shared.game_service, game_id=game_id, on_draw_vote=api_shared.after_draw_vote)
    writer = _Writer()
    session = DaideSession(None, writer, server)
    session.power = power
    session.game_id = game_id
    server.register(game_id, power, session)
    return session, writer


async def _send(session: DaideSession, *tokens_: Token) -> None:
    await session._handle_diplomacy(b"".join(bytes(tok) for tok in tokens_))


def _dms(probe: OutboxProbe) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in probe.rows():
        if r["kind"] == "dm":
            out.setdefault(str(r["telegram_id"]), []).append(r["message"])
    return out


async def test_a_daide_draw_vote_is_announced_to_the_telegram_players() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    session, writer = _daide_seat(game_id, "ENGLAND")

    with OutboxProbe() as probe:
        await _send(session, t.DRW)

    assert writer.frames() == [[t.YES, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN]]
    expected = (
        f"ENGLAND has voted to end game {game_id} in a draw (1/7 agreed). "
        "Draw votes last until this phase is processed. "
        "Use /draw to agree or /nodraw to withdraw."
    )
    # The DAIDE voter has no Telegram id, so nobody is excluded: the player
    # seated as ENGLAND on Telegram did not cast this vote and hears of it too.
    assert _dms(probe) == {tg: [expected] for _h, tg in users}


async def test_a_daide_draw_vote_withdrawal_is_announced() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    session, _writer = _daide_seat(game_id, "ENGLAND")
    with OutboxProbe():
        await _send(session, t.DRW)

    with OutboxProbe() as probe:
        await _send(session, t.NOT, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN)

    expected = f"ENGLAND has withdrawn its vote to end game {game_id} in a draw (0/7 agreed)."
    assert _dms(probe) == {tg: [expected] for _h, tg in users}


async def test_a_draw_completed_over_daide_is_announced_and_seen_by_the_api() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    for power, (headers, _tg) in list(zip(POWERS, users))[:-1]:
        with OutboxProbe():
            r = client.post(f"/games/{game_id}/draw_vote", json={"power": power, "vote": True}, headers=headers)
        assert r.json()["quorum_reached"] is False, r.text
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    # Cache the board while the game is still active: the DAIDE path must
    # invalidate it, as the HTTP route does, or the API keeps serving ACTIVE.
    assert client.get(f"/games/{game_id}/state").json()["status"] == "ACTIVE"
    session, writer = _daide_seat(game_id, "TURKEY")

    with OutboxProbe() as probe:
        await _send(session, t.DRW)

    assert writer.frames() == [[t.YES, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN], [t.DRW]]
    # Every power shares the draw, so each reads itself as "you" (BD4), and the
    # Telegram TURKEY is told too: the deciding vote came from a DAIDE client.
    def shared_by_you(power: str) -> str:
        others = [p for p in sorted(POWERS) if p != power]
        return f"Game {game_id} has ended in a draw shared by you, {', '.join(others[:-1])} and {others[-1]}."

    assert _dms(probe) == {tg: [shared_by_you(power)] for power, (_h, tg) in zip(POWERS, users)}
    drawn = f"Game {game_id} has ended in a draw shared by AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA and TURKEY."
    assert [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "channel_text"] == [
        (GROUP, f"🤝 Draw - Game {game_id}\n{drawn}")
    ]
    assert client.get(f"/games/{game_id}/state").json()["status"] == "COMPLETED"


def test_the_api_wires_the_daide_listener_to_the_draw_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIPLOMACY_DAIDE_PORT", "0")
    with TestClient(app):
        daide: Any = api_shared.daide_server
        assert daide is not None
        assert daide.on_draw_vote is api_shared.after_draw_vote
