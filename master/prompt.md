You are working on my fork sa2ajj/buildbot, branch pb-interop-flake-diagnostics.

Goal: add PB interop-only diagnostics for flaky tests without affecting other integration tests.

Constraints:
- Do NOT overwrite buildbot/test/util/integration.py. Make only additive/minimal edits.
- Diagnostics must run only when:
  - self.proto == "pb"
  - and the test module starts with "buildbot.test.integration.interop."
- Use Twisted logging only: twisted.python.log.msg / log.err (no stdlib logging).
- Enable DelayedCall.debug for those tests, restore it in cleanup.
- On test failure (trial sets self._passed == False), dump pending delayed calls.
- Mypy must pass on Windows typing: call getDelayedCalls via cast(IReactorCore, reactor).
- Keep output low-noise: only dump delayed calls on failure.

Tasks:
1) Open buildbot/test/util/integration.py, locate class RunMasterBase(unittest.TestCase).
2) Add needed imports (cast, DelayedCall, IReactorCore).
3) Add RunMasterBase.setUp() override + helper(s) implementing the above.
4) Run formatting/lint/mypy as you normally do, then commit:
   "tests: add PB interop delayed call diagnostics"
