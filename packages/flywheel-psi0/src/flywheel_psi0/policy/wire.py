"""The JSON the author's `serve_psi0_simple` speaks on `POST /act`, without importing psi.

Mirrors `psi.deploy.helpers` and `psi.deploy.serve_psi0_simple` (the
`serve_psi0_simple` entry point) at the pin cda3fdf: a numpy array travels as
`{"__numpy__": <base64 of its bytes>, "dtype": <numpy descr>, "shape": [...]}`,
nested anywhere in the message. A request carries `image` (camera name to HxWx3
uint8), `instruction`, `history`, `state` (`{"states": (N, Ds) float32}`),
`condition`, `gt_action`, `dataset_name` and `timestamp`; the response carries
`action`, the next `(Ta, Da)` de-normalised actions, and `err`.

With `--rtc` the server keeps ONE previous chunk and lets one client own it,
identified by `history["session_id"]` (what SIMPLE's own eval client sends);
`history["reset"]` drops that chunk and takes the session over. Without a session
id the server falls back to the client's host, so two rollouts from one machine
would get 409s or chunks conditioned on each other's.
"""

from __future__ import annotations

import time
from base64 import b64decode, b64encode
from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray


def encode(value: Any) -> Any:
    """Every numpy array or scalar inside `value` in the wire form, recursively."""
    if isinstance(value, (np.ndarray, np.generic)):
        array = np.ascontiguousarray(value)
        return {
            "__numpy__": b64encode(array.tobytes()).decode(),
            # numpy.lib.format.dtype_to_descr is dtype.str for every non-structured dtype.
            "dtype": array.dtype.str,
            "shape": list(array.shape),
        }
    if isinstance(value, Mapping):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


def decode(value: Any) -> Any:
    """The inverse of `encode`: wire-form arrays back to numpy, recursively."""
    if isinstance(value, Mapping):
        if "__numpy__" in value:
            array = np.frombuffer(b64decode(value["__numpy__"]), np.dtype(value["dtype"]))
            shape = value["shape"]
            return array.reshape(shape) if shape else array[0]
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def request(
    images: Mapping[str, NDArray[np.uint8]],
    states: NDArray[np.floating],
    instruction: str,
    session_id: str,
    reset: bool = False,
    dataset_name: str = "",
) -> dict[str, Any]:
    """One `/act` request body, as `RequestMessage.serialize()` builds it."""
    history: dict[str, Any] = {"session_id": session_id}
    if reset:
        history["reset"] = True
    body: dict[str, Any] = encode(
        {
            "image": dict(images),
            "instruction": instruction,
            "history": history,
            "state": {"states": np.asarray(states, dtype=np.float32).reshape(1, -1)},
            "condition": {},
            "gt_action": [],
            "dataset_name": dataset_name,
            "timestamp": str(time.time()),
        }
    )
    return body


def response_actions(body: Any) -> NDArray[np.float64]:
    """The `(Ta, Da)` actions of an `/act` response; the server's error string raises."""
    decoded = decode(body)
    if not isinstance(decoded, Mapping) or "action" not in decoded:
        # serve_psi0_simple answers a failed request with '{"status": "<error>"}'.
        raise RuntimeError(f"psi0 server error: {body!r}")
    return np.asarray(decoded["action"], dtype=np.float64)
