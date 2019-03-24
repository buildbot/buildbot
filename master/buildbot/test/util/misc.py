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

import os
import sys

from twisted.internet import threads
from twisted.python import log
from twisted.python import threadpool
from twisted.python.compat import NativeStringIO
from twisted.trial.unittest import TestCase

import buildbot
from buildbot.process.buildstep import BuildStep
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.util.eventual import _setReactor


class PatcherMixin:

    """
    Mix this in to get a few special-cased patching methods
    """

    def patch_os_uname(self, replacement):
        # twisted's 'patch' doesn't handle the case where an attribute
        # doesn't exist..
        if hasattr(os, 'uname'):
            self.patch(os, 'uname', replacement)
        else:
            def cleanup():
                del os.uname
            self.addCleanup(cleanup)
            os.uname = replacement


class StdoutAssertionsMixin:

    """
    Mix this in to be able to assert on stdout during the test
    """

    def setUpStdoutAssertions(self):
        self.stdout = NativeStringIO()
        self.patch(sys, 'stdout', self.stdout)

    def assertWasQuiet(self):
        self.assertEqual(self.stdout.getvalue(), '')

    def assertInStdout(self, exp):
        self.assertIn(exp, self.stdout.getvalue())

    def getStdout(self):
        return self.stdout.getvalue().strip()


class TestReactorMixin:

    """
    Mix this in to get TestReactor as self.reactor which is correctly cleaned up
    at the end
    """
    def setUpTestReactor(self):
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()
        _setReactor(self.reactor)

        def deferToThread(f, *args, **kwargs):
            return threads.deferToThreadPool(self.reactor, self.reactor.getThreadPool(),
                                             f, *args, **kwargs)
        self.patch(threads, 'deferToThread', deferToThread)

        # During shutdown sequence we must first stop the reactor and only then
        # set unset the reactor used for eventually() because any callbacks
        # that are run during reactor.stop() may use eventually() themselves.
        self.addCleanup(_setReactor, None)
        self.addCleanup(self.reactor.stop)


class TimeoutableTestCase(TestCase):
    # The addCleanup in current Twisted does not time out any functions
    # registered via addCleanups. Until we can depend on fixed Twisted, use
    # TimeoutableTestCase whenever test failure may cause it to block and not
    # report anything.

    def deferRunCleanups(self, ignored, result):
        self._deferRunCleanupResult = result
        d = self._run('deferRunCleanupsTimeoutable', result)
        d.addErrback(self._ebGotMaybeTimeout, result)
        return d

    def _ebGotMaybeTimeout(self, failure, result):
        result.addError(self, failure)

    def deferRunCleanupsTimeoutable(self):
        return super().deferRunCleanups(None, self._deferRunCleanupResult)


def encodeExecutableAndArgs(executable, args, encoding="utf-8"):
    """
    Encode executable and arguments from unicode to bytes.
    This avoids a deprecation warning when calling reactor.spawnProcess()
    """
    if isinstance(executable, str):
        executable = executable.encode(encoding)

    argsBytes = []
    for arg in args:
        if isinstance(arg, str):
            arg = arg.encode(encoding)
        argsBytes.append(arg)

    return (executable, argsBytes)


def enable_trace(case, trace_exclusions=None, f=sys.stdout):
    """This function can be called to enable tracing of the execution
    """
    if trace_exclusions is None:
        trace_exclusions = [
            "twisted", "worker_transition.py", "util/tu", "util/path",
            "log.py", "/mq/", "/db/", "buildbot/data/", "fake/reactor.py"
        ]

    bbbase = os.path.dirname(buildbot.__file__)
    state = {'indent': 0}

    def tracefunc(frame, event, arg):
        if frame.f_code.co_filename.startswith(bbbase):
            if not any(te in frame.f_code.co_filename for te in trace_exclusions):
                if event == "call":
                    state['indent'] += 2
                    print("-" * state['indent'], frame.f_code.co_filename.replace(bbbase, ""),
                          frame.f_code.co_name, frame.f_code.co_varnames, file=f)
                if event == "return":
                    state['indent'] -= 2
        return tracefunc

    sys.settrace(tracefunc)
    case.addCleanup(sys.settrace, lambda _a, _b, _c: None)


class DebugIntegrationLogsMixin:

    def setupDebugIntegrationLogs(self):
        # to ease debugging we display the error logs in the test log
        origAddCompleteLog = BuildStep.addCompleteLog

        def addCompleteLog(self, name, _log):
            if name.endswith("err.text"):
                log.msg("got error log!", name, _log)
            return origAddCompleteLog(self, name, _log)
        self.patch(BuildStep, "addCompleteLog", addCompleteLog)

        if 'BBTRACE' in os.environ:
            enable_trace(self)
