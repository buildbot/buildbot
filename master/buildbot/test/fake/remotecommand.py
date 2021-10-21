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

from buildbot.process.results import CANCELLED
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS


class FakeRemoteCommand:

    # callers should set this to the running TestCase instance
    testcase = None

    active = False

    interrupted = False

    _waiting_for_interrupt = False

    def __init__(self, remote_command, args,
                 ignore_updates=False, collectStdout=False, collectStderr=False,
                 decodeRC=None,
                 stdioLogName='stdio'):
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        # copy the args and set a few defaults
        self.remote_command = remote_command
        self.args = args.copy()
        self.logs = {}
        self._log_close_when_finished = {}
        self.delayedLogs = {}
        self.rc = -999
        self.collectStdout = collectStdout
        self.collectStderr = collectStderr
        self.updates = {}
        self.decodeRC = decodeRC
        self.stdioLogName = stdioLogName
        if collectStdout:
            self.stdout = ''
        if collectStderr:
            self.stderr = ''

    @defer.inlineCallbacks
    def run(self, step, conn, builder_name):
        if self._waiting_for_interrupt:
            yield step.interrupt('interrupt reason')
            if not self.interrupted:
                raise RuntimeError("Interrupted step, but command was not interrupted")

        # delegate back to the test case
        cmd = yield self.testcase._remotecommand_run(self, step, conn, builder_name)
        for name, log_ in self.logs.items():
            if self._log_close_when_finished[name]:
                log_.finish()
        return cmd

    def useLog(self, log_, closeWhenFinished=False, logfileName=None):
        if not logfileName:
            logfileName = log_.getName()
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.logs[logfileName] = log_
        self._log_close_when_finished[logfileName] = closeWhenFinished

    def useLogDelayed(self, logfileName, activateCallBack, closeWhenFinished=False):
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.delayedLogs[logfileName] = (activateCallBack, closeWhenFinished)

    def addStdout(self, data):
        if self.collectStdout:
            self.stdout += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            self.logs[self.stdioLogName].addStdout(data)

    def addStderr(self, data):
        if self.collectStderr:
            self.stderr += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            self.logs[self.stdioLogName].addStderr(data)

    def addHeader(self, data):
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            self.logs[self.stdioLogName].addHeader(data)

    @defer.inlineCallbacks
    def addToLog(self, logname, data):
        # Activate delayed logs on first data.
        if logname in self.delayedLogs:
            (activate_callback, close_when_finished) = self.delayedLogs[logname]
            del self.delayedLogs[logname]
            loog = yield activate_callback(self)
            self.logs[logname] = loog
            self._log_close_when_finished[logname] = close_when_finished

        if logname in self.logs:
            self.logs[logname].addStdout(data)
        else:
            raise Exception("{}.addToLog: no such log {}".format(self, logname))

    def interrupt(self, why):
        if not self._waiting_for_interrupt:
            raise RuntimeError("Got interrupt, but FakeRemoteCommand was not expecting it")
        self._waiting_for_interrupt = False
        self.interrupted = True

    def results(self):
        if self.interrupted:
            return CANCELLED
        if self.rc in self.decodeRC:
            return self.decodeRC[self.rc]
        return FAILURE

    def didFail(self):
        return self.results() == FAILURE

    def set_run_interrupt(self):
        self._waiting_for_interrupt = True

    def __repr__(self):
        return "FakeRemoteCommand(" + repr(self.remote_command) + "," + repr(self.args) + ")"


class FakeRemoteShellCommand(FakeRemoteCommand):

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=20 * 60, maxTime=None, sigtermTime=None, logfiles=None,
                 usePTY=None, logEnviron=True, collectStdout=False,
                 collectStderr=False,
                 interruptSignal=None, initialStdin=None, decodeRC=None,
                 stdioLogName='stdio'):
        if logfiles is None:
            logfiles = {}
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        args = dict(workdir=workdir, command=command, env=env or {},
                    want_stdout=want_stdout, want_stderr=want_stderr,
                    initial_stdin=initialStdin,
                    timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                    usePTY=usePTY, logEnviron=logEnviron)

        if interruptSignal is not None and interruptSignal != 'KILL':
            args['interruptSignal'] = interruptSignal
        super().__init__("shell", args,
                         collectStdout=collectStdout,
                         collectStderr=collectStderr,
                         decodeRC=decodeRC,
                         stdioLogName=stdioLogName)
