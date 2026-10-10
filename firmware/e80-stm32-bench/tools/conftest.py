"""Host-side pytest glue for the tools/ suite.

Why this exists
---------------
``test_giftwrap_determinism_spec.py`` (card t_c4c43d76) marks its coroutine
tests with ``@pytest.mark.asyncio`` and its header documents a bare
``python3 -m pytest -q test_giftwrap_determinism_spec.py`` run — but the repo
declares no async plugin anywhere, so in a clean environment those tests fail
with pytest's *"async def functions are not natively supported"* instead of
exercising the code they pin.  Declaring an undeclared third-party plugin as a
hidden prerequisite would make the suite environment-dependent; running the
coroutines here keeps ``make range-test-host`` self-contained.

If ``pytest-asyncio`` (or another async plugin) is installed it registers the
same ``pytest_pyfunc_call`` hook and may win the firstresult race — either way
the test body executes exactly once on a fresh event loop.
"""

import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    """Run coroutine test functions on a private event loop.

    Returns ``None`` for synchronous tests so pytest's default machinery (or an
    async plugin) keeps handling them.
    """
    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None

    argnames = getattr(pyfuncitem._fixtureinfo, "argnames", ())
    kwargs = {name: pyfuncitem.funcargs[name] for name in argnames
              if name in pyfuncitem.funcargs}
    asyncio.run(testfunction(**kwargs))
    return True
