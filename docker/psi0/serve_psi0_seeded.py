"""Serve Psi0 like `serve_psi0_simple`, but seed the policy noise per episode (docs/he/tray.md 8.5).

Run inside the Psi0 environment, with the same arguments as `serve_psi0_simple`:

    python serve_psi0_seeded.py --policy psi0 --run-dir ... --port 22085 ...

Psi0 @ cda3fdf seeds the global RNG once at startup (serve_psi0_simple.py line 66) and draws its
flow-matching noise from the global `torch.randn` (psi0.py lines 1986, 2127, 2275, 2433), so two
runs of one condition get different noise. Clients that send `history["seed"]` with `reset`
(flywheel_simple.tray.run, #90) ask for the noise of that episode to start from that seed. This
launcher wraps `Server.predict_action` before `Server.run()` binds it to `/act` (line 470): on a
request with `reset` and `seed` it calls `torch.manual_seed(seed)` and
`torch.cuda.manual_seed_all(seed)`, then delegates. Requests without a seed behave as before.
Psi0's source is not edited.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any


def seed_from_payload(payload: Any) -> int | None:
    """Episode seed of a /act payload: `history.seed` on a `history.reset` request, else None."""
    history = payload.get("history") if isinstance(payload, dict) else None
    if not isinstance(history, dict) or not history.get("reset") or history.get("seed") is None:
        return None
    return int(history["seed"])


def seeded(
    predict_action: Callable[..., Any], seed_fn: Callable[[int], None]
) -> Callable[..., Any]:
    """Wrap `Server.predict_action(self, payload, http_request)` to seed before a new episode.

    functools.wraps keeps `__wrapped__`, so inspect.signature (and FastAPI, which reads the
    signature of the bound method) still sees `(payload, http_request)` with their annotations.
    """

    @functools.wraps(predict_action)
    def wrapper(self: Any, payload: Any, *args: Any, **kwargs: Any) -> Any:
        seed = seed_from_payload(payload)
        if seed is not None:
            seed_fn(seed)
        return predict_action(self, payload, *args, **kwargs)

    return wrapper


def install(server_cls: type, seed_fn: Callable[[int], None]) -> None:
    """Patch `server_cls.predict_action` in place; must run before `server_cls.run()`."""
    server_cls.predict_action = seeded(server_cls.predict_action, seed_fn)  # type: ignore[attr-defined]


def torch_seed(seed: int) -> None:
    import torch  # type: ignore[import-not-found]  # only in the Psi0 environment

    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def main() -> None:
    from psi.deploy import serve_psi0_simple  # type: ignore[import-not-found]

    install(serve_psi0_simple.Server, torch_seed)
    serve_psi0_simple.main()  # reads sys.argv[1:] like the `serve_psi0_simple` entry point


if __name__ == "__main__":
    main()
