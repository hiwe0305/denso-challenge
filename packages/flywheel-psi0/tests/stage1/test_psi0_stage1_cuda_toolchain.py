"""`cuda_toolchain.match` on a faked VM: the CUDA 13.0 VM of attempt 1, a matching one."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from flywheel_psi0.stage1 import cuda_toolchain
from flywheel_psi0.stage1.cuda_toolchain import compatible, match, toolkit_packages

VENV = Path("/content/da30/Psi0/.venv-psi/bin")
SYSTEM_PATH = "/usr/local/bin:/usr/bin"  # where the system pip puts ninja on Colab
NVCC = "nvcc: NVIDIA (R) Cuda compiler driver\nCuda compilation tools, release {}, V{}.41\n"


class FakeVM:
    """nvcc per CUDA_HOME, torch's CUDA, ninja on some PATH dirs; apt and pip change them."""

    def __init__(self, system: str | None, torch: str = "12.6", ninja_in: str = str(VENV)):
        self.nvcc = {"/usr/local/cuda": system} if system else {}
        self.torch = torch
        self.ninja_dirs = {ninja_in}
        self.commands: list[str] = []
        self.apt_fails = 0

    def run(self, command: Sequence[str]) -> str | None:
        if command[0] == str(VENV / "python"):
            return f"{self.torch}\n"
        version = self.nvcc.get(str(Path(command[0]).parents[1]))
        return NVCC.format(version, version) if version else None

    def sh(self, command: str, cwd: Path | None = None, env: object = None) -> None:
        self.commands.append(command)
        if command.startswith("apt-get install"):
            if self.apt_fails:
                self.apt_fails -= 1
                raise subprocess.CalledProcessError(100, command)
            self.nvcc[f"/usr/local/cuda-{self.torch}"] = self.torch
        if "pip install" in command:
            self.ninja_dirs.add("/usr/local/bin")

    def which(self, name: str, path: str | None = None) -> str | None:
        if name == "nvcc":
            return None  # torch falls back to /usr/local/cuda
        dirs = (path or "").split(":")
        return next((f"{d}/ninja" for d in dirs if d in self.ninja_dirs), None)

    def match(self) -> dict[str, object]:
        environ = {"PATH": SYSTEM_PATH}
        return match(VENV, sh=self.sh, run=self.run, which=self.which, environ=environ)


def test_deepspeeds_rule() -> None:
    assert compatible("12.6", "12.6") and compatible("12.4", "12.6")
    assert not compatible("13.0", "12.6")  # attempt 1
    assert not compatible("12.9", "12.6")  # 12.9 is not in DeepSpeed 0.17.1's list
    assert toolkit_packages("12.6") == [
        "cuda-nvcc-12-6",
        "cuda-cudart-dev-12-6",
        "libcurand-dev-12-6",
        "libcublas-dev-12-6",
    ]


def test_a_cuda_13_vm_gets_torchs_toolkit() -> None:
    vm = FakeVM("13.0")
    report = vm.match()
    assert vm.commands == ["apt-get install -y -q " + " ".join(toolkit_packages("12.6"))]
    assert report["system_cuda"] == "13.0" and report["torch_cuda"] == "12.6"
    assert report["installed"] == toolkit_packages("12.6")
    assert report["env"] == {
        "CUDA_HOME": "/usr/local/cuda-12.6",
        "PATH": f"/usr/local/cuda-12.6/bin:{VENV}:{SYSTEM_PATH}",
    }


def test_a_matching_vm_installs_nothing_and_still_puts_the_venv_first() -> None:
    vm = FakeVM("12.6")
    report = vm.match()
    assert vm.commands == [] and report["installed"] == []
    # The venv's ninja first on PATH: attempt 1's second failure.
    assert report["env"] == {"PATH": f"{VENV}:{SYSTEM_PATH}"}
    assert report["cuda_home"] == "/usr/local/cuda"


def test_no_nvcc_at_all_is_a_mismatch() -> None:
    report = FakeVM(None).match()
    assert report["system_cuda"] is None and report["installed"] == toolkit_packages("12.6")


def test_no_ninja_anywhere_is_pip_installed() -> None:
    vm = FakeVM("12.6", ninja_in="/nowhere")
    report = vm.match()
    assert vm.commands == ["python3 -m pip install -q ninja"]
    assert report["installed"] == ["ninja (pip)"]


def test_stale_package_lists_are_refreshed_once() -> None:
    vm = FakeVM("13.0")
    vm.apt_fails = 1
    vm.match()
    install = "apt-get install -y -q " + " ".join(toolkit_packages("12.6"))
    assert vm.commands == [install, "apt-get update -q", install]


def test_a_toolkit_that_still_mismatches_stops_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    vm = FakeVM("13.0")
    monkeypatch.setattr(vm, "sh", lambda command, cwd=None, env=None: None)  # apt did nothing
    with pytest.raises(SystemExit, match="reports CUDA None after the install"):
        vm.match()


def test_a_cpu_torch_stops_setup() -> None:
    vm = FakeVM("13.0", torch="None")
    with pytest.raises(SystemExit, match="no CUDA build"):
        vm.match()


def test_capture_returns_none_for_a_missing_binary() -> None:
    assert cuda_toolchain.capture(["/nonexistent/nvcc", "-V"]) is None
