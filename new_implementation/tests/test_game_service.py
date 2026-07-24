"""M6 checkpoint A: the new-engine game service over state_json persistence."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from persistence.game_repo import GameRepo
from server.game_service import GameService

pytestmark = pytest.mark.database


@pytest.fixture
def service(temp_db):
    """A GameService bound to the test database."""
    session_factory = sessionmaker(bind=temp_db)
    return GameService(GameRepo(session_factory))


def _new_game(service) -> str:
    gid = f"gs-{uuid.uuid4().hex[:8]}"
    service.create_game(gid)
    return gid


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
