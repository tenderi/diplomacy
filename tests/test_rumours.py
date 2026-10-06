"""Rumours (#157): a broadcast sent anonymously.

It reaches every seated player by DM -- the sender too, with the same text, so
the one player without a DM can't be picked out as the author -- and the
game's linked Telegram group when ``auto_post_broadcasts`` is on -- but no DM,
group post or API read names the sender to anyone but the sender themself.
Signed broadcasts reach the linked group too, and keep naming their sender.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.shared import db_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_anonymous_games import _BOT, _as, _game

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

GROUP = "-1004441570001"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _linked(client: TestClient, *, auto_post: bool = True) -> tuple[str, str, str, str]:
    """``_game`` (Anna FRANCE, Bert GERMANY; public) linked to ``GROUP``."""
    game_id, anna, bert, bert_nick = _game(client, anonymous=False)
    r = client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers={**_BOT, "X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200, r.text
    if not auto_post:
        db_service.update_game_channel_settings(game_id, {"auto_post_broadcasts": False})
    return game_id, anna, bert, bert_nick


def _group_posts(probe: OutboxProbe) -> list[tuple[str, str]]:
    return [(r["kind"], r["message"]) for r in probe.rows() if str(r["telegram_id"]) == GROUP]


class TestTheLinkedGroup:
    def test_a_broadcast_is_posted_to_the_linked_group_naming_the_sender(self, client: TestClient) -> None:
        game_id, _, bert, bert_nick = _linked(client)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Peace"))
        assert r.status_code == 200, r.text
        assert _group_posts(probe) == [
            ("channel_text", f"📢 Broadcast in game {game_id} from GERMANY ({bert_nick}): Peace"),
        ]

    def test_a_rumour_is_posted_to_the_linked_group_naming_nobody(self, client: TestClient) -> None:
        game_id, _, bert, _ = _linked(client)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Italy will stab", anonymous=True))
        assert r.status_code == 200, r.text
        assert _group_posts(probe) == [("channel_text", f"🕵️ Rumour in game {game_id}: Italy will stab")]

    @pytest.mark.parametrize("anonymous", [True, False])
    def test_nothing_reaches_the_group_with_auto_post_broadcasts_off(self, client: TestClient, anonymous: bool) -> None:
        game_id, _, bert, _ = _linked(client, auto_post=False)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Peace", anonymous=anonymous))
        assert r.status_code == 200, r.text
        assert _group_posts(probe) == []


class TestRumours:
    @pytest.mark.parametrize("game_anonymous", [True, False])
    def test_the_dm_names_nobody_and_reaches_the_sender_too(self, client: TestClient, game_anonymous: bool) -> None:
        # The sender gets exactly one DM, byte-identical to everyone else's:
        # left out, they were the one player with no DM (#173).
        game_id, anna, bert, _ = _game(client, anonymous=game_anonymous)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Italy will stab", anonymous=True))
        assert r.status_code == 200, r.text
        dm = f"🕵️ Rumour in game {game_id}: Italy will stab"
        assert probe.by_recipient() == {anna: [dm], bert: [dm]}

    def test_a_signed_broadcast_still_skips_its_sender(self, client: TestClient) -> None:
        game_id, anna, bert, bert_nick = _game(client, anonymous=False)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Peace"))
        assert r.status_code == 200, r.text
        assert probe.by_recipient() == {anna: [f"Broadcast in game {game_id} from GERMANY ({bert_nick}): Peace"]}

    def test_the_rumour_is_stored_anonymous_with_its_sender(self, client: TestClient) -> None:
        game_id, _, bert, _ = _game(client, anonymous=False)
        r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Italy will stab", anonymous=True))
        assert r.status_code == 200, r.text
        row = db_service.get_game_by_game_id(game_id)
        stored = [
            (m.anonymous, m.sender_user_id, m.recipient_power, m.text)
            for m in db_service.get_messages_by_game_id(int(row.id)).all()
        ]
        assert stored == [(True, db_service.get_user_by_telegram_id(bert).id, None, "Italy will stab")]

    def test_a_signed_broadcast_is_stored_signed(self, client: TestClient) -> None:
        game_id, _, bert, _ = _game(client, anonymous=False)
        assert client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Peace")).status_code == 200
        row = db_service.get_game_by_game_id(game_id)
        assert [m.anonymous for m in db_service.get_messages_by_game_id(int(row.id)).all()] == [False]

    def test_the_log_hides_the_sender_from_everyone_but_the_sender(self, client: TestClient) -> None:
        game_id, anna, bert, bert_nick = _game(client, anonymous=False)
        client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Peace"))
        client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Italy will stab", anonymous=True))

        def log(params: dict) -> list[tuple]:
            r = client.get(f"/games/{game_id}/messages", params=params)
            assert r.status_code == 200, r.text
            return [
                (m["sender_power"], m["sender_name"], m["sender_user_id"] is not None, m["anonymous"], m["text"])
                for m in r.json()["messages"]
            ]

        signed = ("GERMANY", bert_nick, True, False, "Peace")
        rumour_hidden = (None, None, False, True, "Italy will stab")
        assert log(_as(anna)) == [signed, rumour_hidden]
        assert log({}) == [signed, rumour_hidden]
        assert log(_as(bert)) == [signed, ("GERMANY", bert_nick, True, True, "Italy will stab")]

    def test_a_broadcast_to_an_unknown_game_is_404(self, client: TestClient) -> None:
        _, _, bert, _ = _game(client, anonymous=False)
        r = client.post("/games/999999999/broadcast", json=_as(bert, text="Hello?", anonymous=True))
        assert (r.status_code, r.json()["detail"]) == (404, "Game not found")
