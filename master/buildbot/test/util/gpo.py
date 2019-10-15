# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.internet import defer
from twisted.internet import utils


def _check_env_is_expected(test, expected_env, env):
    if expected_env is None:
        return

    env = env or {}
    for var, value in expected_env.items():
        test.assertEqual(env.get(var), value,
                         'Expected environment to have %s = %r' % (var, value))


class Expect:
    _stdout = b""
    _stderr = b""
    _exit = 0
    _path = None
    _env = None

    def __init__(self, bin, *args):
        self._bin = bin
        self._args = args

    def stdout(self, stdout):
        assert(isinstance(stdout, bytes))
        self._stdout = stdout
        return self

    def stderr(self, stderr):
        assert(isinstance(stderr, bytes))
        self._stderr = stderr
        return self

    def exit(self, exit):
        self._exit = exit
        return self

    def path(self, path):
        self._path = path
        return self

    def env(self, env):
        self._env = env
        return self

    def check(self, test, bin, path, args, env):
        test.assertDictEqual(
            dict(bin=bin, path=path, args=tuple(args)),
            dict(bin=self._bin, path=self._path, args=self._args), "unexpected command run")

        _check_env_is_expected(test, self._env, env)
        return (self._stdout, self._stderr, self._exit)

    def __repr__(self):
        return "<gpo.Expect(bin=%s, args=%s)>" % (self._bin, self._args)


class GetProcessOutputMixin:
    longMessage = True

    def setUpGetProcessOutput(self):
        self._gpo_patched = False
        self._expected_commands = []
        self._gpo_expect_env = {}

    def assertAllCommandsRan(self):
        self.assertEqual(self._expected_commands, [],
                         "assert all expected commands were run")

    @defer.inlineCallbacks
    def patched_getProcessOutput(self, bin, args, env=None,
                                 errortoo=False, path=None):
        stdout, stderr, exit = \
            yield self.patched_getProcessOutputAndValue(bin, args, env=env,
                                                        path=path)
        if errortoo:
            return stdout + stderr
        if stderr:
            raise IOError("got stderr: %r" % (stderr,))
        return stdout

    def patched_getProcessOutputAndValue(self, bin, args, env=None,
                                         path=None):
        _check_env_is_expected(self, self._gpo_expect_env, env)

        if not self._expected_commands:
            self.fail("got command %s %s when no further commands were expected"
                      % (bin, args))

        expect = self._expected_commands.pop(0)
        return defer.succeed(expect.check(self, bin, path, args, env))

    def _patch_gpo(self):
        if not self._gpo_patched:
            self.patch(utils, "getProcessOutput",
                       self.patched_getProcessOutput)
            self.patch(utils, "getProcessOutputAndValue",
                       self.patched_getProcessOutputAndValue)
            self._gpo_patched = True

    def addGetProcessOutputExpectEnv(self, d):
        self._gpo_expect_env.update(d)

    def expectCommands(self, *exp):
        """
        Add to the expected commands, along with their results.  Each
        argument should be an instance of L{Expect}.
        """
        self._patch_gpo()
        self._expected_commands.extend(exp)
