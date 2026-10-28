"""Dev-only stand-in for cuRobo so SIMPLE imports on a machine without CUDA build tools.

SIMPLE imports cuRobo when it loads any robot, even in sim_mode=mujoco where no
motion planning runs. This package satisfies those imports for scene, reset and
success-check work (S1-02, DA-32). Any attribute resolves to a placeholder that raises
on use, so a code path that really needs planning fails loudly. Install the real
cuRobo on a CUDA machine for data generation (DA-33).
"""

import importlib.abc
import importlib.machinery
import sys
import types

_MESSAGE = "cuRobo stub: this needs the real cuRobo on a CUDA machine (see docs/g0/env-simple.md)"


class _Placeholder:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(_MESSAGE)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


def _placeholder(name: str) -> type:
    return type(name, (_Placeholder,), {"__module__": "curobo"})


class _StubModule(types.ModuleType):
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        value = _placeholder(name)
        setattr(self, name, value)
        return value


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith("curobo."):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _StubModule(spec.name)
        module.__path__ = []
        return module

    def exec_module(self, module):
        pass


IS_STUB = True
sys.meta_path.insert(0, _StubFinder())
sys.modules[__name__].__class__ = _StubModule
