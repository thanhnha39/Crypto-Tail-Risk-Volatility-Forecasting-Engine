import sys, types, runpy
try:
    import pytest  # noqa
    sys.exit(__import__("pytest").main(["-q", "tests"]))
except ImportError:
    m = types.ModuleType("pytest")
    class _M:
        def __init__(s, n, a): s.name, s.args = n, a
    def parametrize(*a):
        def deco(f):
            f.pytestmark = getattr(f, "pytestmark", []) + [_M("parametrize", a)]
            return f
        return deco
    m.mark = types.SimpleNamespace(parametrize=parametrize)
    sys.modules["pytest"] = m
    runpy.run_path("tests/test_leakage.py", run_name="__main__")
