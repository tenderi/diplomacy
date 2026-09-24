"""``server.response_cache`` -- the TTL + LRU cache behind ``@cached_response``.

A fake clock replaces ``time.time`` so expiry is tested without sleeping. Whether the
routes *invalidate* it at the right moments is ``test_cache_coherence.py``.
"""
from __future__ import annotations

import threading
from typing import Any

import pytest

from server import response_cache
from server.response_cache import ResponseCache, cached_response, clear_response_cache, invalidate_cache

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(response_cache.time, "time", fake)
    return fake


@pytest.fixture
def cache() -> ResponseCache:
    return ResponseCache(default_ttl=60, max_size=10)


class TestPutAndGet:
    def test_hit_miss_and_stats(self, cache: ResponseCache, clock: Clock) -> None:
        cache.put("ep", {"v": 1}, params={"game_id": "7"})
        assert cache.get("ep", {"game_id": "7"}) == {"v": 1}
        assert cache.get("ep", {"game_id": "8"}) is None
        stats = cache.get_stats()
        assert (stats["hit_count"], stats["miss_count"], stats["hit_rate"], stats["cache_size"]) == (1, 1, 0.5, 1)

    def test_the_key_ignores_parameter_order(self, cache: ResponseCache) -> None:
        cache.put("ep", "x", params={"a": 1, "b": 2})
        assert cache.get("ep", {"b": 2, "a": 1}) == "x"

    def test_entries_expire_after_their_ttl(self, cache: ResponseCache, clock: Clock) -> None:
        cache.put("short", "s", ttl=5)
        cache.put("default", "d")
        clock.now += 5
        assert cache.get("short") == "s"
        clock.now += 1
        assert cache.get("short") is None
        assert cache.get("default") == "d"
        clock.now += 60
        assert cache.cleanup_expired() == 1
        assert cache.get_stats()["cache_size"] == 0

    @pytest.mark.parametrize("ttl", [0, -1])
    def test_a_non_positive_ttl_caches_nothing(self, cache: ResponseCache, ttl: int) -> None:
        cache.put("ep", "x", ttl=ttl)
        assert cache.get("ep") is None

    def test_a_full_cache_evicts_the_least_recently_read(self, cache: ResponseCache, clock: Clock) -> None:
        for i in range(10):
            clock.now += 1
            cache.put(f"ep{i}", i)
        clock.now += 1
        assert cache.get("ep0") == 0  # read: now the most recent
        cache.put("ep10", 10)
        assert cache.get_stats()["cache_size"] == 10
        assert cache.get("ep1") is None  # the least recently used went
        assert cache.get("ep0") == 0 and cache.get("ep10") == 10


class TestInvalidation:
    def test_a_route_path_pattern_clears_that_game_only(self, cache: ResponseCache) -> None:
        state = "server.api.routes.games.get_game_state"
        cache.put(state, "seven", params={"game_id": "7"})
        cache.put(state, "eight", params={"game_id": "8"})
        cache.put("server.api.routes.users.get_user_games", "mine", params={"telegram_id": "555"})
        cache.invalidate_pattern("games/7")
        assert cache.get(state, {"game_id": "7"}) is None
        assert cache.get(state, {"game_id": "8"}) == "eight"
        cache.invalidate_pattern("users/555")
        assert cache.get("server.api.routes.users.get_user_games", {"telegram_id": "555"}) is None

    def test_module_helpers_act_on_the_shared_cache(self) -> None:
        clear_response_cache()
        response_cache._response_cache.put("server.api.routes.games.get_players", [1], params={"game_id": "3"})
        invalidate_cache("games/3")
        assert response_cache._response_cache.get("server.api.routes.games.get_players", {"game_id": "3"}) is None
        response_cache._response_cache.put("x", 1)
        clear_response_cache()
        assert response_cache.get_cache_stats()["cache_size"] == 0


class TestDecorator:
    @pytest.fixture(autouse=True)
    def _fresh(self) -> Any:
        clear_response_cache()
        yield
        clear_response_cache()

    def test_caches_per_key_param_value(self) -> None:
        calls: list[str] = []

        @cached_response(ttl=60, key_params=["game_id"])
        def state(game_id: str, viewer: str = "anyone") -> dict:
            calls.append(game_id)
            return {"game": game_id}

        assert state(game_id="7") == {"game": "7"}
        assert state(game_id="7", viewer="someone else") == {"game": "7"}  # not a key param
        assert state(game_id="8") == {"game": "8"}
        assert calls == ["7", "8"]

    def test_a_positional_call_is_keyed_by_the_same_param(self) -> None:
        """Keying only on kwargs made ``state("8")`` share ``state("7")``'s entry."""
        @cached_response(ttl=60, key_params=["game_id"])
        def state(game_id: str) -> dict:
            return {"game": game_id}

        assert state("7") == {"game": "7"}
        assert state("8") == {"game": "8"}
        assert state(game_id="7") == {"game": "7"}

    def test_an_exception_is_not_cached(self) -> None:
        calls = {"n": 0}

        @cached_response(ttl=60)
        def flaky(x: int) -> int:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("first call fails")
            return x

        with pytest.raises(ValueError):
            flaky(1)
        assert flaky(1) == 1 and flaky(1) == 1
        assert calls["n"] == 2


def test_concurrent_writers_never_overfill_it() -> None:
    cache = ResponseCache(default_ttl=60, max_size=50)

    def write(worker: int) -> None:
        for i in range(200):
            cache.put(f"ep{worker}-{i}", i)
            cache.get(f"ep{worker}-{i // 2}")

    threads = [threading.Thread(target=write, args=(w,)) for w in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(cache.cache) <= 50
    assert set(cache.cache) == set(cache.access_times) == set(cache.cache_params)
