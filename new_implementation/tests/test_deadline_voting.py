"""Majority-vote deadline proposals: POST .../deadline/{propose,vote,withdraw}.

Any single player could already set a game's deadline unilaterally
(``POST .../deadline``) -- that stays, unchanged. This is the alternative for a
table that would rather decide the pace together: a power proposes a value (or
clearing it), the proposer's own yes vote is cast automatically, and it resolves
the moment a **majority** (not unanimity, unlike a draw vote) of active powers --
non-eliminated, with a unit, the same population ``GameService.active_powers``
gives a draw vote's quorum -- votes yes. A majority of no votes rejects it early
(mathematically no yes-majority is possible any more); an optional per-proposal
``vote_hours`` expiry, swept by ``api.shared.expire_deadline_proposals`` from the
scheduler loop, fails it the same way if nobody reaches majority in time. Only
one proposal may be pending per game; a second is refused until the first
resolves or its proposer withdraws it.
"""
from __future__ import annotations

import itertools
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared

pytestmark = [pytest.mark.integration, pytest.mark.database]

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
_seq = itertools.count(1)


def _register(client: TestClient, tag: str) -> dict:
    stamp = f"{int(time.time() * 1000000)}_{tag}_{next(_seq)}"
    resp = client.post(
        "/auth/register", json={"email": f"dlv_{stamp}@example.com", "password": "testpass123"}
    )
    if resp.status_code != 200:
        pytest.skip("Database not available for deadline-voting test")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seeded_game(client: TestClient) -> tuple[str, dict[str, dict]]:
    """A game with all seven powers held by distinct users. Returns
    ``(game_id, {power: headers})``."""
    users = {p: _register(client, p) for p in POWERS}
    resp = client.post(
        "/games/create", json={"map_name": "standard", "initial_phase": "Movement"},
        headers=users["FRANCE"],
    )
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    for power, headers in users.items():
        r = client.post(f"/games/{game_id}/join", json={"power": power}, headers=headers)
        assert r.status_code == 200, f"join {power}: {r.text}"
    return game_id, users


def test_propose_casts_the_proposers_own_yes_vote():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    resp = client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "FRANCE", "hours": 24.0}, headers=users["FRANCE"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["yes_votes"] == ["FRANCE"]
    assert body["needed_for_majority"] == 4  # majority of 7
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is not None


def test_only_one_proposal_pending_at_a_time():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    assert client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "FRANCE", "hours": 24.0}, headers=users["FRANCE"],
    ).status_code == 200
    resp = client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "GERMANY", "hours": 6.0}, headers=users["GERMANY"],
    )
    assert resp.status_code == 400
    assert "already pending" in resp.json()["detail"]


def test_majority_yes_applies_the_deadline_and_clears_the_proposal():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    assert client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "FRANCE", "hours": 24.0}, headers=users["FRANCE"],
    ).status_code == 200

    # FRANCE (auto) + 2 more = 3/7, not yet a majority.
    for power in ["GERMANY", "ITALY"]:
        r = client.post(
            f"/games/{game_id}/deadline/vote", json={"power": power, "vote": True}, headers=users[power]
        )
        assert r.json()["status"] == "pending", r.text

    # The 4th yes vote reaches majority (4/7) and resolves it.
    r = client.post(
        f"/games/{game_id}/deadline/vote", json={"power": "ENGLAND", "vote": True}, headers=users["ENGLAND"]
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"

    state = client.get(f"/games/{game_id}/deadline").json()
    assert state["pending_proposal"] is None
    assert state["deadline"] is not None
    deadline = datetime.fromisoformat(state["deadline"]).replace(tzinfo=timezone.utc)
    remaining = deadline - datetime.now(timezone.utc)
    assert timedelta(hours=23) < remaining < timedelta(hours=25)


def test_majority_no_rejects_without_changing_anything():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    assert client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "FRANCE", "hours": 6.0}, headers=users["FRANCE"],
    ).status_code == 200

    # FRANCE auto-voted yes; with 7 active powers and a majority of 4 needed,
    # yes could still theoretically reach 4 (FRANCE + all 3 remaining
    # undecided) until a 3rd no vote is cast.
    for power in ["GERMANY", "ITALY", "RUSSIA"]:
        r = client.post(
            f"/games/{game_id}/deadline/vote", json={"power": power, "vote": False}, headers=users[power]
        )
        assert r.json()["status"] == "pending", r.text

    # The 4th no vote (TURKEY) makes a yes-majority mathematically
    # impossible (1 yes + 2 remaining undecided < 4 needed): reject early.
    r = client.post(
        f"/games/{game_id}/deadline/vote", json={"power": "TURKEY", "vote": False}, headers=users["TURKEY"]
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"

    state = client.get(f"/games/{game_id}/deadline").json()
    assert state["pending_proposal"] is None
    assert state["deadline"] is None


def test_clearing_deadline_via_majority_vote():
    """value_hours=None (propose "clear") applies as clearing the deadline."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    # Give it a deadline first, unilaterally, the old way.
    assert client.post(
        f"/games/{game_id}/deadline", json={"deadline": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()},
        headers=users["FRANCE"],
    ).status_code == 200

    assert client.post(
        f"/games/{game_id}/deadline/propose", json={"power": "FRANCE"}, headers=users["FRANCE"],
    ).status_code == 200
    for power in ["GERMANY", "ITALY", "ENGLAND"]:
        client.post(f"/games/{game_id}/deadline/vote", json={"power": power, "vote": True}, headers=users[power])

    state = client.get(f"/games/{game_id}/deadline").json()
    assert state["deadline"] is None


def test_only_the_proposer_can_withdraw():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    assert client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "AUSTRIA", "hours": 10.0}, headers=users["AUSTRIA"],
    ).status_code == 200

    resp = client.post(
        f"/games/{game_id}/deadline/withdraw", json={"power": "TURKEY"}, headers=users["TURKEY"]
    )
    assert resp.status_code == 400
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is not None

    resp = client.post(
        f"/games/{game_id}/deadline/withdraw", json={"power": "AUSTRIA"}, headers=users["AUSTRIA"]
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "withdrawn"
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is None


def test_only_the_assigned_player_may_propose_or_vote_for_a_power():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    resp = client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "GERMANY", "hours": 6.0}, headers=users["FRANCE"],
    )
    assert resp.status_code == 403

    assert client.post(
        f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 6.0}, headers=users["FRANCE"],
    ).status_code == 200
    resp = client.post(
        f"/games/{game_id}/deadline/vote",
        json={"power": "GERMANY", "vote": True}, headers=users["FRANCE"],
    )
    assert resp.status_code == 403


def test_vote_with_no_pending_proposal_is_refused():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    resp = client.post(
        f"/games/{game_id}/deadline/vote", json={"power": "FRANCE", "vote": True}, headers=users["FRANCE"]
    )
    assert resp.status_code == 400


def test_expired_proposal_is_cleared_without_a_majority():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    resp = client.post(
        f"/games/{game_id}/deadline/propose",
        json={"power": "ITALY", "hours": 5.0, "vote_hours": 1.0}, headers=users["ITALY"],
    )
    assert resp.status_code == 200
    assert resp.json()["vote_deadline"] is not None

    # Not yet expired: the sweep leaves it alone.
    api_shared.expire_deadline_proposals(datetime.now(timezone.utc))
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is not None

    # Past the vote's own deadline: the sweep clears it, nothing applied.
    api_shared.expire_deadline_proposals(datetime.now(timezone.utc) + timedelta(hours=2))
    state = client.get(f"/games/{game_id}/deadline").json()
    assert state["pending_proposal"] is None
    assert state["deadline"] is None


def test_proposal_with_no_vote_hours_never_expires():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    resp = client.post(
        f"/games/{game_id}/deadline/propose", json={"power": "ITALY", "hours": 5.0}, headers=users["ITALY"],
    )
    assert resp.json()["vote_deadline"] is None
    # Even a "sweep from the far future" leaves a no-expiry proposal pending.
    api_shared.expire_deadline_proposals(datetime.now(timezone.utc) + timedelta(days=365))
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is not None
