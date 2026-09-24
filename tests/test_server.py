"""The text-command CLI surface (``server.server.Server.process_command``), driven end
to end against the database: create, add a player, order, process, read the state."""
import pytest

from server.server import Server
from tests.conftest import _get_db_url

pytestmark = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@pytest.fixture
def server() -> Server:
    return Server()


def test_create_and_query_game(server: Server) -> None:
    result = server.process_command("CREATE_GAME standard")
    assert result["status"] == "ok"
    state = server.process_command(f"GET_GAME_STATE {result['game_id']}")
    assert state["status"] == "ok"
    assert (state["state"]["map_name"], state["state"]["phase"]) == ("standard", "S1901M")


def test_new_game_defaults_to_the_standard_map(server: Server) -> None:
    assert server.process_command("NEW_GAME")["map_name"] == "standard"


def test_orders_accumulate_and_a_turn_consumes_them(server: Server) -> None:
    game_id = server.process_command("CREATE_GAME standard")["game_id"]
    assert server.process_command(f"ADD_PLAYER {game_id} FRANCE")["status"] == "ok"
    assert server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")["status"] == "ok"
    assert server.process_command(f"SET_ORDERS {game_id} FRANCE A MAR - SPA")["status"] == "ok"
    assert sorted(server.process_command(f"GET_GAME_STATE {game_id}")["state"]["orders"]["FRANCE"]) == ["A MAR - SPA", "A PAR - BUR"]

    assert server.process_command(f"PROCESS_TURN {game_id}")["status"] == "ok"
    state = server.process_command(f"GET_GAME_STATE {game_id}")["state"]
    assert (state["phase"], state["orders"]) == ("F1901M", {})
    assert {"BUR", "SPA"} <= {u["location"] for u in state["units_by_power"]["FRANCE"]}


def test_an_invalid_order_is_refused_and_keeps_the_good_ones(server: Server) -> None:
    game_id = server.process_command("CREATE_GAME standard")["game_id"]
    server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    result = server.process_command(f"SET_ORDERS {game_id} FRANCE A MAR - MOS")
    assert (result["status"], result["error_code"]) == ("error", "INVALID_ORDER")
    assert result["order"] == "A MAR - MOS"
    assert server.process_command(f"GET_GAME_STATE {game_id}")["state"]["orders"]["FRANCE"] == ["A PAR - BUR"]


@pytest.mark.parametrize("command", ["ADD_PLAYER 999999999 FRANCE", "SET_ORDERS 999999999 FRANCE A PAR H",
                                     "PROCESS_TURN 999999999", "GET_GAME_STATE 999999999"])
def test_unknown_game(server: Server, command: str) -> None:
    assert server.process_command(command)["error_code"] == "GAME_NOT_FOUND"


@pytest.mark.parametrize("command", ["", "ADD_PLAYER", "ADD_PLAYER 1", "SET_ORDERS 1 FRANCE", "PROCESS_TURN", "GET_GAME_STATE"])
def test_missing_arguments(server: Server, command: str) -> None:
    assert server.process_command(command)["error_code"] == "MISSING_ARGUMENTS"


def test_unknown_command(server: Server) -> None:
    result = server.process_command("FOO_BAR")
    assert result["error_code"] == "UNKNOWN_COMMAND"
    assert "Unknown command" in result["message"]
