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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

from twisted.internet import defer
from twisted.internet import utils


class Expect(object):
    _stdout = ""
    _stderr = ""
    _exit = 0
    _path = None

    def __init__(self, bin, *args):
        self._bin = bin
        self._args = args

    def stdout(self, stdout):
        self._stdout = stdout
        return self

    def stderr(self, stderr):
        self._stderr = stderr
        return self

    def exit(self, exit):
        self._exit = exit
        return self

    def path(self, path):
        self._path = path
        return self

    def check(self, test, bin, path, args):
        test.assertDictEqual(
            dict(bin=bin, path=path, args=tuple(args)),
            dict(bin=self._bin, path=self._path, args=self._args), "unexpected command run")
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

    def _check_env(self, env):
        env = env or {}
        for var, value in iteritems(self._gpo_expect_env):
            self.assertEqual(env.get(var), value,
                             'Expected environment to have %s = %r' % (var, value))

    def patched_getProcessOutput(self, bin, args, env=None,
                                 errortoo=False, path=None):
        d = self.patched_getProcessOutputAndValue(bin, args, env=env,
                                                  path=path)

        @d.addCallback
        def cb(res):
            stdout, stderr, exit = res
            if errortoo:
                return defer.succeed(stdout + stderr)
            if stderr:
                return defer.fail(IOError("got stderr: %r" % (stderr,)))
            return defer.succeed(stdout)
        return d

    def patched_getProcessOutputAndValue(self, bin, args, env=None,
                                         path=None):
        self._check_env(env)

        if not self._expected_commands:
            self.fail("got command %s %s when no further commands were expected"
                      % (bin, args))

        expect = self._expected_commands.pop(0)
        return defer.succeed(expect.check(self, bin, path, args))

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
