"""CD1: a power that is out (conceded) is not DMed requests it cannot act on.

A draw vote or a deadline proposal asks the table to vote; a conceded power has no
vote. The conceding player's own reply and the game-ended announcement are unchanged.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.reliability_helpers import OutboxProbe
from tests.test_draw_concede_notifications import POWERS, _recipients, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _concede_turkey(client: TestClient):
    game_id, users = _seeded_game(client)
    headers, tg = users[POWERS.index("TURKEY")]
    with OutboxProbe():
        resp = client.post(f"/games/{game_id}/concede", json={"power": "TURKEY"}, headers=headers)
    assert resp.status_code == 200, resp.text
    return game_id, users, tg


def test_draw_vote_and_withdrawal_skip_a_conceded_power() -> None:
    client = TestClient(app)
    game_id, users, turkey_tg = _concede_turkey(client)
    headers, voter_tg = users[0]
    others = {tg for _h, tg in users} - {turkey_tg, voter_tg}
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/draw_vote", json={"power": "ENGLAND", "vote": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    vote = (
        f"ENGLAND has voted to end game {game_id} in a draw (1/6 agreed). "
        "Draw votes last until this phase is processed. Use /draw to agree or /nodraw to withdraw."
    )
    assert _recipients(probe) == {tg: [vote] for tg in others}
    with OutboxProbe() as probe:
        client.post(f"/games/{game_id}/draw_vote", json={"power": "ENGLAND", "vote": False}, headers=headers)
    withdrawn = f"ENGLAND has withdrawn its vote to end game {game_id} in a draw (0/6 agreed)."
    assert _recipients(probe) == {tg: [withdrawn] for tg in others}


def test_deadline_proposal_and_vote_skip_a_conceded_power() -> None:
    client = TestClient(app)
    game_id, users, turkey_tg = _concede_turkey(client)
    headers, proposer_tg = users[POWERS.index("FRANCE")]
    others = {tg for _h, tg in users} - {turkey_tg, proposer_tg}
    with OutboxProbe() as probe:
        resp = client.post(
            f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 24}, headers=headers
        )
    assert resp.status_code == 200, resp.text
    text = (
        f"FRANCE proposes a 24h deadline for game {game_id}, counted from when the proposal passes. "
        f"Needs 4 yes votes (1/4 so far). Use /deadline {game_id} vote yes|no."
    )
    assert _recipients(probe) == {tg: [text] for tg in others}
    g_headers, g_tg = users[POWERS.index("GERMANY")]
    with OutboxProbe() as probe:
        resp = client.post(
            f"/games/{game_id}/deadline/vote", json={"power": "GERMANY", "vote": True}, headers=g_headers
        )
    assert resp.status_code == 200, resp.text
    voted = f"GERMANY voted yes on game {game_id}'s deadline proposal (2/4 needed)."
    assert _recipients(probe) == {tg: [voted] for tg in (others | {proposer_tg}) - {g_tg}}
