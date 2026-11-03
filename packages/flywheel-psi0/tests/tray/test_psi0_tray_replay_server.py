"""The stand-in Psi0 server of the eval replay gate, over real HTTP on CPU (DA-34)."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from flywheel_psi0.tray.replay_server import Replay, decode, encode, make_server


def test_wire_format_round_trips() -> None:
    value = {"a": np.arange(6, dtype=np.float32).reshape(2, 3), "b": [np.int64(4)], "c": "x"}
    back = decode(json.loads(json.dumps(encode(value))))
    np.testing.assert_array_equal(back["a"], value["a"])
    assert back["b"] == [4] and back["c"] == "x"


SAMPLE = Path(__file__).parent / "data" / "simple_client_sample.json"


def test_reads_and_writes_what_simples_client_writes() -> None:
    # Made by SIMPLE b75c678's own client.py (numpy 2.2.6, as CI): a request with an
    # uint8 image and float32 states, a response of 24 x 36 float32, a float64 scalar.
    sample = json.loads(SAMPLE.read_text())
    request = decode(sample["request"])
    assert request["image"]["rgb_head_stereo_left"].dtype == np.uint8
    assert request["image"]["rgb_head_stereo_left"].shape == (2, 3, 3)
    assert request["state"]["states"].dtype == np.float32
    assert request["history"] == {"reset": True, "seed": 1001}
    assert decode(sample["scalar"])["x"] == 0.5
    for key in ("request", "response", "scalar"):
        assert json.loads(json.dumps(encode(decode(sample[key])))) == sample[key]


@pytest.fixture
def served() -> Iterator[tuple[str, Replay]]:
    episodes = [np.arange(50 * 36, dtype=np.float32).reshape(50, 36), np.ones((10, 36), "f4")]
    replay = Replay(episodes, chunk=24)
    server = make_server(replay, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", replay
    server.shutdown()


def _act(url: str, reset: bool) -> np.ndarray:
    request = {"image": {}, "state": {"states": np.zeros((1, 32), "f4")}, "history": {}}
    if reset:
        request["history"] = {"reset": True}
    body = json.dumps(encode(request)).encode()
    with urllib.request.urlopen(urllib.request.Request(f"{url}/act", body)) as response:
        return np.asarray(decode(json.loads(response.read()))["action"])


def test_serves_recorded_frames_in_chunks_then_holds(served: tuple[str, Replay]) -> None:
    url, replay = served
    first = _act(url, reset=True)
    assert first.shape == (24, 36)
    np.testing.assert_array_equal(first, replay.episodes[0][:24])
    np.testing.assert_array_equal(_act(url, reset=False), replay.episodes[0][24:48])
    tail = _act(url, reset=False)  # frames 48, 49, then the last one held
    np.testing.assert_array_equal(tail[:2], replay.episodes[0][48:50])
    np.testing.assert_array_equal(tail[2:], np.repeat(replay.episodes[0][-1:], 22, axis=0))


def test_reset_moves_to_the_next_episode(served: tuple[str, Replay]) -> None:
    url, replay = served
    _act(url, reset=True)
    np.testing.assert_array_equal(_act(url, reset=True), np.ones((24, 36), "f4"))
    with pytest.raises(urllib.error.HTTPError):
        _act(url, reset=True)  # the queue has two episodes


def test_info_names_the_replay(served: tuple[str, Replay]) -> None:
    url, _ = served
    with urllib.request.urlopen(f"{url}/info") as response:
        assert json.loads(response.read())["policy"] == "replay"
