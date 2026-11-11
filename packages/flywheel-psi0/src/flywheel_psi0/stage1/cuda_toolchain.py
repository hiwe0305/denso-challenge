"""Give DeepSpeed's CPU Adam build a CUDA toolkit that matches torch (DA-30, 11/11/2026).

The pre-flight and the run build DeepSpeed's CPU Adam op just in time. DeepSpeed 0.17.1
(`op_builder/builder.py`, `assert_no_cuda_mismatch`) refuses to build when the `nvcc`
under torch's CUDA_HOME reports another CUDA than the one torch was built with, unless
both are in the same major's compatible list; the build then needs a `ninja` on PATH.

Attempt 1 of branch B (11/11/2026) got a Colab VM with CUDA 13.0 while the pinned
torch 2.7.0 is cu126: the pre-flight failed on the mismatch, then on a missing ninja
(the venv's ninja was not on PATH), and passed once the matching toolkit was installed
by hand. `match` does the same before the pre-flight: when the system CUDA does not
pass DeepSpeed's check, it installs torch's toolkit from the VM's NVIDIA apt repo, and
returns the CUDA_HOME and PATH that `setup` gives the pre-flight and writes for `run`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

Shell = Callable[..., None]
Capture = Callable[[Sequence[str]], "str | None"]

# DeepSpeed 0.17.1, op_builder/builder.py `cuda_minor_mismatch_ok`: within one major,
# a system CUDA and a torch CUDA both in this list are accepted.
MINOR_MISMATCH_OK: dict[int, frozenset[str]] = {
    10: frozenset({"10.0", "10.1", "10.2"}),
    11: frozenset(f"11.{minor}" for minor in range(9)),
    12: frozenset({"12.0", "12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.8"}),
}
# What the hand fix of attempt 1 installed: nvcc, and the headers CPU Adam includes.
TOOLKIT_PACKAGES = ("cuda-nvcc", "cuda-cudart-dev", "libcurand-dev", "libcublas-dev")
RELEASE = re.compile(r"release (\d+)\.(\d+)")
TORCH_CUDA = "import torch; print(torch.version.cuda)"


def capture(command: Sequence[str]) -> str | None:
    """stdout of `command`, or None when it is missing or fails."""
    try:
        return subprocess.run(list(command), capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def major_minor(version: str) -> str:
    return ".".join(version.strip().split(".")[:2])


def compatible(system: str, torch: str) -> bool:
    """DeepSpeed's `assert_no_cuda_mismatch`, on major.minor strings."""
    if system == torch:
        return True
    major = int(system.split(".")[0])
    allowed = MINOR_MISMATCH_OK.get(major, frozenset())
    return torch.split(".")[0] == system.split(".")[0] and {system, torch} <= allowed


def default_cuda_home(environ: Mapping[str, str], which: Callable[[str], str | None]) -> Path:
    """Where torch looks (`torch.utils.cpp_extension._find_cuda_home`)."""
    home = environ.get("CUDA_HOME") or environ.get("CUDA_PATH")
    if home:
        return Path(home)
    nvcc = which("nvcc")
    return Path(nvcc).resolve().parents[1] if nvcc else Path("/usr/local/cuda")


def nvcc_release(cuda_home: Path, run: Capture) -> str | None:
    output = run([str(cuda_home / "bin" / "nvcc"), "-V"])
    found = RELEASE.search(output or "")
    return f"{found[1]}.{found[2]}" if found else None


def toolkit_packages(cuda: str) -> list[str]:
    return [f"{name}-{cuda.replace('.', '-')}" for name in TOOLKIT_PACKAGES]


def match(
    venv_bin: Path,
    *,
    sh: Shell,
    run: Capture = capture,
    which: Callable[..., str | None] = shutil.which,
    environ: Mapping[str, str] = os.environ,
) -> dict[str, Any]:
    """Make the CUDA under CUDA_HOME pass DeepSpeed's check and put a ninja on PATH.

    Returns what `setup` records in `report.json`: the two CUDA versions, what was
    installed, and `env` (CUDA_HOME when it changed, PATH always: the venv's bin first,
    where the venv's ninja is). Raises SystemExit when torch has no CUDA or the toolkit
    still does not match after the install.
    """
    torch_out = run([str(venv_bin / "python"), "-c", TORCH_CUDA])
    if not torch_out or torch_out.strip() in ("", "None"):
        raise SystemExit(f"torch in {venv_bin} reports no CUDA build ({torch_out!r})")
    torch_cuda = major_minor(torch_out)
    home = default_cuda_home(environ, which)
    system_cuda = nvcc_release(home, run)
    report: dict[str, Any] = {
        "torch_cuda": torch_cuda,
        "system_cuda": system_cuda,
        "system_cuda_home": str(home),
        "installed": [],
    }
    env: dict[str, str] = {}
    path = os.pathsep.join([str(venv_bin), environ.get("PATH", os.defpath)])
    if system_cuda is None or not compatible(system_cuda, torch_cuda):
        packages = toolkit_packages(torch_cuda)
        install = "apt-get install -y -q " + " ".join(packages)
        try:
            sh(install)
        except subprocess.CalledProcessError:
            # Stale package lists on a fresh VM: refresh once, then the same install.
            sh("apt-get update -q")
            sh(install)
        home = Path(f"/usr/local/cuda-{torch_cuda}")
        got = nvcc_release(home, run)
        if got != torch_cuda:
            raise SystemExit(
                f"{home}/bin/nvcc reports CUDA {got} after the install, torch {torch_cuda}"
            )
        report["installed"] = packages
        env["CUDA_HOME"] = str(home)
        path = os.pathsep.join([str(home / "bin"), path])
    if which("ninja", path=path) is None:
        sh("python3 -m pip install -q ninja")
        report["installed"] = [*report["installed"], "ninja (pip)"]
        if which("ninja", path=path) is None:
            raise SystemExit(f"no ninja on PATH after `pip install ninja`: {path}")
    env["PATH"] = path
    report["cuda_home"] = env.get("CUDA_HOME", str(home))
    report["env"] = env
    return report
