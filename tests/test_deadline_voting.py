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
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from persistence import database_service
from persistence.database import GameModel
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


# ---------------------------------------------------------------------------
# v2.7.97: range checks, the accepted deadline, reminders, finished games
# ---------------------------------------------------------------------------


def _accept(client: TestClient, game_id: str, users: dict[str, dict]) -> dict:
    """Three more yes votes after the proposer's: a majority of 7."""
    for power in ("ENGLAND", "GERMANY", "ITALY"):
        resp = client.post(
            f"/games/{game_id}/deadline/vote", json={"power": power, "vote": True}, headers=users[power]
        )
        assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.parametrize(
    "field,raw",
    [
        ("hours", "-5"),        # won its vote, it set a deadline 5 h in the past
        ("hours", "0"),
        ("hours", "721"),
        ("hours", "1e12"),      # accepted into the vote; the deciding yes then 500'd
        ("hours", "NaN"),       # 500 on propose
        ("vote_hours", "-1"),
        ("vote_hours", "Infinity"),  # 500 on propose
    ],
)
def test_out_of_range_hours_are_refused_up_front(field: str, raw: str):
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    body = '{"power": "FRANCE", "hours": 24, "%s": %s}' % (field, raw)
    resp = client.post(
        f"/games/{game_id}/deadline/propose", content=body,
        headers={**users["FRANCE"], "content-type": "application/json"},
    )
    assert resp.status_code == 400, resp.text
    assert "at most 720" in resp.json()["detail"]
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is None


def test_accepted_proposal_returns_the_deadline_it_set():
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    client.post(f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 12.0}, headers=users["FRANCE"])
    body = _accept(client, game_id, users)
    assert body["status"] == "accepted"
    applied = datetime.fromisoformat(body["deadline"]).replace(tzinfo=None)
    assert timedelta(hours=11, minutes=59) < applied - before < timedelta(hours=12, minutes=1)
    stored = datetime.fromisoformat(client.get(f"/games/{game_id}/deadline").json()["deadline"])
    assert abs(stored - applied) < timedelta(seconds=1)


def test_accepted_proposal_rearms_the_ten_minute_reminder():
    """A reminder already sent for the old deadline must not suppress the new one's,
    exactly as a unilateral POST .../deadline already guaranteed."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    numeric_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.reminder_sent[numeric_id] = True
    client.post(f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 1.0}, headers=users["FRANCE"])
    assert _accept(client, game_id, users)["status"] == "accepted"
    assert api_shared.reminder_sent[numeric_id] is False


def test_finished_game_takes_no_deadline_writes():
    from tests.test_api_game_over import BOT_SECRET, _drawn_game

    client = TestClient(app)
    game_id, tg = _drawn_game(client)
    auth = {"telegram_id": tg, "bot_secret": BOT_SECRET}
    propose = client.post(f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 1, **auth})
    assert propose.status_code == 409, propose.text
    vote = client.post(f"/games/{game_id}/deadline/vote", json={"power": "FRANCE", "vote": True, **auth})
    assert vote.status_code == 409, vote.text
    unilateral = client.post(f"/games/{game_id}/deadline", json={"deadline": "2030-01-01T00:00:00", **auth})
    assert unilateral.status_code == 409, unilateral.text
    state = client.get(f"/games/{game_id}/deadline").json()
    assert state["deadline"] is None and state["pending_proposal"] is None


def test_a_failed_apply_leaves_the_proposal_pending(monkeypatch):
    """The deciding vote used to clear the proposal *before* writing the deadline,
    so a failing write lost the vote with nothing changed and nobody told. Both
    are one transaction now; the failure is injected into its deadline write."""
    client = TestClient(app, raise_server_exceptions=False)
    game_id, users = _seeded_game(client)
    client.post(f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 12.0}, headers=users["FRANCE"])
    for power in ("ENGLAND", "GERMANY"):
        client.post(f"/games/{game_id}/deadline/vote", json={"power": power, "vote": True}, headers=users[power])

    def boom(*_args: object) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(database_service, "_naive_utc", boom)
    resp = client.post(f"/games/{game_id}/deadline/vote", json={"power": "ITALY", "vote": True}, headers=users["ITALY"])
    assert resp.status_code == 500
    monkeypatch.undo()
    pending = client.get(f"/games/{game_id}/deadline").json()["pending_proposal"]
    assert pending is not None and pending["yes_votes"] == ["ENGLAND", "FRANCE", "GERMANY"]


def test_two_votes_cast_together_are_both_counted():
    """Each vote read the proposal and wrote it back separately: ITALY's vote,
    committed while GERMANY's was in flight, was erased -- a majority could be
    reached and never noticed. Here a second session holds the row and records
    ITALY's vote while GERMANY's waits."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    client.post(f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 12.0}, headers=users["FRANCE"])
    other = api_shared.db_service.session_factory()
    row = other.query(GameModel).filter_by(game_id=str(game_id)).with_for_update().one()

    thread = threading.Thread(
        target=lambda: api_shared.vote_on_deadline_proposal(str(game_id), int(row.id), "GERMANY", True)
    )
    thread.start()
    time.sleep(0.5)
    proposal = dict(row.pending_deadline_proposal)
    row.pending_deadline_proposal = {**proposal, "votes": {**proposal["votes"], "ITALY": "yes"}}
    other.commit()
    other.close()
    thread.join(timeout=10)
    pending = client.get(f"/games/{game_id}/deadline").json()["pending_proposal"]
    assert pending["yes_votes"] == ["FRANCE", "GERMANY", "ITALY"]
