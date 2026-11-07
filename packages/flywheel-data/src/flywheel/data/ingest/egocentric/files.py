"""Write a work-dir file whole or not at all (review of PR 152).

A step that fails half way (a model that stops answering, a comparison that raises)
must not leave a mix of old and new files. Writers fill a temporary file beside the
target, which `os.replace` swaps in only when the writer finished; the steps also
compute everything before they write anything.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def replacing(path: Path) -> Iterator[Path]:
    """A temporary path beside `path`; it becomes `path` only if the block finishes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_text(path: Path, text: str) -> None:
    with replacing(path) as temporary:
        temporary.write_text(text, encoding="utf-8")
