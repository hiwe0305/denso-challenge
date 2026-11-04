"""Runtime fixes to Psi0 at the pin, applied without editing the Psi0 checkout.

`restore_shuffle`: `e91e1e7` (4/9/2026) dropped `shuffle = True` from
`PretrainTrainer.create_dataloaders` but kept the line that reads it, so for a
dataset without a mixture sampler (EgoDex, HE) `shuffle` is read before it is
assigned and stage 1 stops with `UnboundLocalError` before its first step. The
method is recompiled from Psi0's own source with that line reading `True`, the
value it had before `e91e1e7`; line numbers in tracebacks stay those of the file.

Standard library only: `loader_check` uses it in Psi0's environment without
importing the flywheel contracts.
"""

from __future__ import annotations
import __future__

import inspect
import sys
import textwrap
from collections.abc import Callable
from typing import Any

SHUFFLE_READ = 'train_dataloader_kwargs["shuffle"] = shuffle'
SHUFFLE_FIXED = 'train_dataloader_kwargs["shuffle"] = True'


def restore_shuffle(cls: type) -> bool:
    """Patch `cls.create_dataloaders` if it reads `shuffle` that it never sets to True.

    Returns whether it patched: not when `shuffle = True` is back (fixed upstream) or
    the read is gone. Raises when the read appears more than once, so a reworked
    method is looked at instead of patched blindly.
    """
    method: Callable[..., Any] = cls.create_dataloaders  # type: ignore[attr-defined]
    lines, first_line = inspect.getsourcelines(method)
    source = textwrap.dedent("".join(lines))
    if SHUFFLE_READ not in source or "shuffle = True" in source:
        return False
    if source.count(SHUFFLE_READ) != 1:
        raise RuntimeError(f"{cls.__name__}.create_dataloaders changed; review the shuffle patch")
    module = sys.modules[cls.__module__]
    code = compile(
        "\n" * (first_line - 1) + source.replace(SHUFFLE_READ, SHUFFLE_FIXED),
        inspect.getsourcefile(method) or "<create_dataloaders>",
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    namespace: dict[str, Any] = {}
    exec(code, vars(module), namespace)
    cls.create_dataloaders = namespace["create_dataloaders"]  # type: ignore[attr-defined]
    return True
