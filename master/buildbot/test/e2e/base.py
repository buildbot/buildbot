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

import os
import re
import socket
from io import BytesIO

from fastjsonrpc.client import Proxy
from fastjsonrpc.client import jsonrpc
from txrequests import Session

from twisted.internet import reactor as global_reactor
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import task
from twisted.internet import utils
from twisted.python import log as twisted_python_log
from twisted.trial import unittest
from zope.interface import Interface
from zope.interface import implementer

from buildbot.test.util import dirs
from buildbot.test.util.logging import LoggingMixin
from buildbot.util.indent import indent
from buildbot.util.logger import Logger

try:
    from shutil import which
except ImportError:
    # Backport of shutil.which() from Python 3.3.
    from shutilwhich import which

log = Logger()


def get_buildslave_executable():
    return which("buildslave")


def get_buildbot_executable():
    return which("buildbot")


def get_buildbot_worker_executable():
    return which("buildbot-worker")


def get_buildbot_worker_py3_executable():
    return os.environ.get('BUILDBOT_TEST_PYTHON3_WORKER_PATH')


buildslave_executable = get_buildslave_executable()
buildbot_worker_executable = get_buildbot_worker_executable()
buildbot_worker_py3_executable = get_buildbot_worker_py3_executable()
buildbot_executable = get_buildbot_executable()


def get_open_port():
    # TODO: This is synchronous code which might be blocking, which is
    # unacceptable in Twisted.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_completion(is_completed_pred,
                        check_interval=0.1, timeout=10, reactor=None):
    if reactor is None:
        reactor = global_reactor

    @defer.inlineCallbacks
    def next_try():
        is_completed = yield defer.maybeDeferred(lambda: is_completed_pred())

        if is_completed:
            caller.stop()
        elif reactor.seconds() - start_time > timeout:
            caller.stop()

            raise RuntimeError("Timeout")

    start_time = reactor.seconds()
    caller = task.LoopingCall(next_try)
    return caller.start(check_interval, now=True)


@defer.inlineCallbacks
def run_command(*args):
    command_str = " ".join(args)
    log.debug("Running command: '{0}'".format(command_str))

    executable_path, args = args[0], args[1:]

    stdout, stderr, exitcode = yield utils.getProcessOutputAndValue(
        executable_path, args)

    if stderr:
        log.debug("stderr:\n{0}".format(indent(stderr, "    ")))
    if stdout:
        log.debug("stdout:\n{0}".format(indent(stdout, "    ")))
    log.debug("Process finished with code {0}".format(exitcode))
    assert exitcode == 0, "command failed: '{0}'".format(command_str)

    defer.returnValue((stdout, stderr))


class IBuildbotProcess(Interface):

    @defer.inlineCallbacks
    def start(self, workdir):
        pass

    @defer.inlineCallbacks
    def stop(self, workdir, force=False):
        pass


@implementer(IBuildbotProcess)
class BuidlbotDeamonizedProcessBase(object):

    def __init__(self, executable, workdir):
        self._executable = executable
        self._started = False
        self._workdir = workdir

    @defer.inlineCallbacks
    def start(self):
        assert not self._started
        stdout, stderr = yield run_command(
            self._executable, 'start', self._workdir)
        self._started = True
        defer.returnValue((stdout, stderr))

    @defer.inlineCallbacks
    def stop(self, force=False):
        assert self._started
        stdout, stderr = yield run_command(
            buildbot_worker_executable, 'stop', self._workdir)
        self._started = False
        defer.returnValue((stdout, stderr))


class BuildbotMasterDeamonizedProcess(BuidlbotDeamonizedProcessBase):

    @defer.inlineCallbacks
    def start(self):
        stdout, _ = yield super(BuildbotMasterDeamonizedProcess, self).start()
        assert (
            "The buildmaster appears to have (re)started correctly" in stdout)

    @defer.inlineCallbacks
    def stop(self, force=False):
        stdout, _ = yield super(
            BuildbotMasterDeamonizedProcess, self).stop(force)
        assert re.match(r"buildbot process \d+ is dead", stdout)


class BuildbotWorkerDeamonizedProcess(BuidlbotDeamonizedProcessBase):

    @defer.inlineCallbacks
    def start(self):
        stdout, _ = yield super(BuildbotWorkerDeamonizedProcess, self).start()
        assert (
            "The buildbot-worker appears to have (re)started correctly" in
            stdout)

    @defer.inlineCallbacks
    def stop(self, force=False):
        stdout, _ = yield super(
            BuildbotWorkerDeamonizedProcess, self).stop(force)
        assert re.match(r"worker process \d+ is dead", stdout)


class BuildbotSlaveDeamonizedProcess(BuidlbotDeamonizedProcessBase):

    @defer.inlineCallbacks
    def start(self):
        stdout, _ = yield super(BuildbotSlaveDeamonizedProcess, self).start()
        assert (
            "The buildslave appears to have (re)started correctly" in stdout)

    @defer.inlineCallbacks
    def stop(self, force=False):
        stdout, _ = yield super(
            BuildbotSlaveDeamonizedProcess, self).stop(force)
        assert re.match(r"buildslave process \d+ is dead", stdout)


class EverythingGetter(protocol.ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred
        self.outBuf = BytesIO()
        self.errBuf = BytesIO()
        self.outReceived = self.outBuf.write
        self.errReceived = self.errBuf.write

    def processEnded(self, reason):
        out = self.outBuf.getvalue()
        err = self.errBuf.getvalue()
        e = reason.value
        code = e.exitCode

        if err:
            log.debug("stderr:\n{0}".format(indent(err, "    ")))
        if out:
            log.debug("stdout:\n{0}".format(indent(out, "    ")))
        log.debug("Process finished with code {0}".format(code))

        if e.signal:
            self.deferred.errback((out, err, e.signal))
        else:
            self.deferred.callback((out, err, code))


def check_log_for_marks(logfile, fail_marks, started_marks):
    if not os.path.exists(logfile):
        return

    with open(logfile, 'rt') as f:
        log_contents = f.read()

    for fail_mark in fail_marks:
        if fail_mark in log_contents:
            log.debug("Found fail mark {!r}".format(fail_mark))
            return 'fail'

    for started_mark in started_marks:
        if started_mark in log_contents:
            log.debug("Found start mark {!r}".format(started_mark))
            return 'started'


@implementer(IBuildbotProcess)
class BuidlbotNotDeamonizedProcessBase(object):

    def __init__(self, executable, workdir, fail_marks, started_marks,
                 reactor=None):
        self._executable = executable
        self._started = False
        self._workdir = workdir
        self._logfile = os.path.join(self._workdir, 'twistd.log')
        self._fail_marks = fail_marks
        self._started_marks = started_marks
        self._process_deferred = None
        self._process_transport = None

        self._reactor = reactor or global_reactor

    @defer.inlineCallbacks
    def start(self):
        assert not self._started

        self._process_deferred = defer.Deferred()
        self._process_transport = EverythingGetter(self._process_deferred)

        result = {}

        @self._process_deferred.addBoth
        def onProcessEnd(res):
            result['process_ended'] = res
            return res

        args = self._executable, 'start', '--nodaemon', self._workdir
        log.debug("Running command: '{0}'".format(
            ' '.join(args)))
        self._reactor.spawnProcess(
            self._process_transport,
            self._executable,
            args)

        def is_completed():
            if result:
                return True

            # There is no easy crossplatform name to follow file contents,
            # do polling.
            found_mark = check_log_for_marks(
                self._logfile, self._fail_marks, self._started_marks)
            if found_mark is not None:
                result['mark_found'] = found_mark
                return True

            return False

        yield wait_for_completion(is_completed)

        if 'process_ended' in result:
            assert False, "Processes unexpectedly ended"

        if result['mark_found'] == 'fail':
            assert False, "Process startup failed"

        self._started = True

    @defer.inlineCallbacks
    def stop(self, force=False):
        assert self._started

        if force:
            self._process_transport.transport.signalProcess('KILL')
        else:
            self._process_transport.transport.signalProcess('TERM')

            stdout, stderr, exitcode = yield self._process_deferred

            assert exitcode == 0, "Exited with code {!r}".format(exitcode)

        self._started = False
        self._process_deferred = None
        self._process_transport = None


class BuildbotMasterNotDeamonizedProcess(BuidlbotNotDeamonizedProcessBase):

    def __init__(self, executable, workdir, reactor=None):
        # Based on buildbot/scripts/logwatcher.py
        fail_marks = [
            "reconfig aborted",
            "reconfig partially applied",
            "Server Shut Down",
            "BuildMaster startup failed",
        ]
        started_marks = [
            "message from master: attached",
            "configuration update complete",
            "BuildMaster is running",
        ]

        super(BuildbotMasterNotDeamonizedProcess, self).__init__(
            executable, workdir, fail_marks, started_marks, reactor=reactor)


class BuildbotWorkerNotDeamonizedProcess(BuidlbotNotDeamonizedProcessBase):

    def __init__(self, executable, workdir, reactor=None):
        fail_marks = [
            "Server Shut Down",
        ]
        started_marks = [
            "Connecting to",
        ]

        super(BuildbotWorkerNotDeamonizedProcess, self).__init__(
            executable, workdir, fail_marks, started_marks, reactor=reactor)


class BuildbotSlaveNotDeamonizedProcess(BuidlbotNotDeamonizedProcessBase):

    def __init__(self, executable, workdir, reactor=None):
        fail_marks = [
            "Server Shut Down",
        ]
        started_marks = [
            "Connecting to",
        ]

        super(BuildbotSlaveNotDeamonizedProcess, self).__init__(
            executable, workdir, fail_marks, started_marks, reactor=reactor)


class NoDaemonMixin:
    BuildbotMasterProcess = BuildbotMasterNotDeamonizedProcess
    BuildbotWorkerProcess = BuildbotWorkerNotDeamonizedProcess
    BuildbotSlaveProcess = BuildbotSlaveNotDeamonizedProcess


class DaemonMixin:
    BuildbotMasterProcess = BuildbotMasterDeamonizedProcess
    BuildbotWorkerProcess = BuildbotWorkerDeamonizedProcess
    BuildbotSlaveProcess = BuildbotSlaveDeamonizedProcess


class E2ETestBase(dirs.DirsMixin, NoDaemonMixin, LoggingMixin,
                  unittest.TestCase):

    buildbot_executable = buildbot_executable
    buildbot_worker_executable = buildbot_worker_executable
    buildslave_executable = buildslave_executable

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpLogging()

        self._origcwd = os.getcwd()
        test_name = self.id().rsplit('.', 1)[1]
        self.projectdir = os.path.abspath('project_' + test_name)
        yield self.setUpDirs(self.projectdir)
        os.chdir(self.projectdir)

        self.master_port = get_open_port()
        self.ui_port = get_open_port()

        # Started masters or workers (mapping from workdir to wrapper).
        # Populated when appropriate master or workers are created.
        # Used for test cleanup in case of failure (force stop still running
        # master/worker).
        self.running_master = None
        self.running_workers = {}
        self.running_slaves = {}

        # All created masters/workers/slaves twisted.log files (they are
        # verbosely dumped in case of error, for easier debugging on
        # remote CI).
        self.log_files = []

        self.session = Session()

    @defer.inlineCallbacks
    def tearDown(self):
        self.session.close()

        still_running = (
            self.running_master or self.running_workers or self.running_slaves)

        # Note: self._passed is an Twisted's implementation detail, but there
        # is no other simple way to get test pass/fail status.
        if not self._passed or still_running:
            log.debug(
                "Trying to stop possibly running services")
            yield self._force_stop()

            # Output ran command logs to stdout to help debugging in CI systems
            # where logs are not available (e.g. Travis).
            # Logs can be stored on AppVeyor and CircleCI, we can move
            # e2e tests there if we don't want such output.
            print("Test failed, output:")
            print("-" * 80)
            for event in self._logEvents:
                msg = twisted_python_log.textFromEventDict(event)
                if msg is not None:
                    print(msg)
            print("-" * 80)
            self._print_all_logs()

            os.chdir(self._origcwd)

            if still_running and self._passed:
                # Fail test if not all processes gracefully terminated.
                raise RuntimeError(
                    "One of the started processes not stopped. "
                    "Did you forgot to call teardownEnvironment()?")

        else:
            os.chdir(self._origcwd)

            # Clean working directory only when test succeeded.
            yield self.tearDownDirs()

    @defer.inlineCallbacks
    def _force_stop(self):
        """Force stop running master/workers"""

        for worker in self.running_workers.values():
            try:
                yield worker.stop(force=True)
            except Exception:
                # Ignore errors.
                pass
        self.running_workers = {}

        for slave in self.running_slaves.values():
            try:
                yield slave.stop(force=True)
            except Exception:
                # Ignore errors.
                pass
        self.running_slaves = {}

        if self.running_master is not None:
            try:
                yield self.running_master.stop(force=True)
                self.running_master = None
            except Exception:
                # Ignore errors.
                pass

    def _print_all_logs(self):
        """Print all started services Twistd logs.

        Useful on remote CI where log files are not available after build is
        finished.
        """

        for log_path in self.log_files:
            if os.path.exists(log_path):
                with open(log_path, "rt") as f:
                    print("Log '{}':".format(log_path))
                    print(indent(f.read(), "    "))

    @defer.inlineCallbacks
    def _buildbot_create_master(self, master_dir, buildbot_executable=None):
        """Runs "buildbot create-master" and checks result"""

        buildbot_executable = buildbot_executable or self.buildbot_executable

        self.log_files.append(os.path.join(master_dir, "twistd.log"))
        stdout, _ = yield run_command(
            buildbot_executable, 'create-master', master_dir)
        self.assertIn("buildmaster configured in", stdout)

    @defer.inlineCallbacks
    def _buildbot_worker_create_worker(self, worker_dir, name, password,
                                       buildbot_worker_executable=None):
        buildbot_worker_executable = \
            buildbot_worker_executable or self.buildbot_worker_executable

        self.log_files.append(os.path.join(worker_dir, "twistd.log"))
        master_addr = 'localhost:{port}'.format(port=self.master_port)
        stdout, _ = yield run_command(
            buildbot_worker_executable, 'create-worker', worker_dir,
            master_addr, name, password)
        self.assertIn("worker configured in", stdout)

    @defer.inlineCallbacks
    def _buildslave_create_slave(self, slave_dir, name, password,
                                 buildslave_executable=None):
        buildslave_executable = \
            buildslave_executable or self.buildslave_executable

        self.log_files.append(os.path.join(slave_dir, "twistd.log"))
        master_addr = 'localhost:{port}'.format(port=self.master_port)
        stdout, _ = yield run_command(
            buildslave_executable, 'create-slave', slave_dir,
            master_addr, name, password)
        self.assertIn("buildslave configured in", stdout)

    @defer.inlineCallbacks
    def _buildbot_start(self, master_dir):
        master = self.BuildbotMasterProcess(
            self.buildbot_executable, master_dir)

        yield master.start()

        self.running_master = master

    @defer.inlineCallbacks
    def _buildbot_stop(self, master_dir):
        assert self.running_master is not None

        yield self.running_master.stop()

        self.running_master = None

    @defer.inlineCallbacks
    def _buildbot_worker_start(self, worker_dir,
                               buildbot_worker_executable=None):
        assert worker_dir not in self.running_workers

        buildbot_worker_executable = \
            buildbot_worker_executable or self.buildbot_worker_executable

        worker = self.BuildbotWorkerProcess(
            buildbot_worker_executable, worker_dir)

        yield worker.start()

        self.running_workers[worker_dir] = worker

    @defer.inlineCallbacks
    def _buildbot_worker_stop(self, worker_dir):
        assert worker_dir in self.running_workers

        yield self.running_workers[worker_dir].stop()

        del self.running_workers[worker_dir]

    @defer.inlineCallbacks
    def _buildslave_start(self, slave_dir, buildslave_executable=None):
        assert slave_dir not in self.running_slaves

        buildslave_executable = \
            buildslave_executable or self.buildslave_executable

        slave = self.BuildbotSlaveProcess(
            buildslave_executable, slave_dir)

        yield slave.start()

        self.running_slaves[slave_dir] = slave

    @defer.inlineCallbacks
    def _buildslave_stop(self, slave_dir):
        assert slave_dir in self.running_slaves

        yield self.running_slaves[slave_dir].stop()

        del self.running_slaves[slave_dir]

    @defer.inlineCallbacks
    def _get(self, endpoint):
        uri = 'http://localhost:{port}/api/v2/{endpoint}'.format(
            port=self.ui_port, endpoint=endpoint)
        response = yield self.session.get(uri)
        defer.returnValue(response.json())

    @defer.inlineCallbacks
    def _get_raw(self, endpoint):
        uri = 'http://localhost:{port}/api/v2/{endpoint}'.format(
            port=self.ui_port, endpoint=endpoint)
        response = yield self.session.get(uri)
        defer.returnValue(response.text)

    def _call_rpc(self, endpoint, method, *args, **kwargs):
        uri = 'http://localhost:{port}/api/v2/{endpoint}'.format(
            port=self.ui_port, endpoint=endpoint)
        proxy = Proxy(uri, version=jsonrpc.VERSION_2)
        return proxy.callRemote(method, *args, **kwargs)

    def _write_master_config(self, master_dir, master_cfg):
        """Replaces default ports in config with currently used and
        writes config to master's master.cfg"""

        # Substitute ports to listen with currently used random ports.
        master_cfg = master_cfg.replace('9989', str(self.master_port))
        master_cfg = master_cfg.replace('8010', str(self.ui_port))

        with open(os.path.join(master_dir, 'master.cfg'), 'wt') as f:
            f.write(master_cfg)

    @defer.inlineCallbacks
    def setupEnvironment(self, env):
        assert len(env['masters']) == 1, \
            "Only single master is currently supported"

        master_dir, config, master_exec = env['masters'][0]

        yield self._buildbot_create_master(master_dir, master_exec)
        self._write_master_config(master_dir, config)

        for worker_dir, name, password, worker_exec in env.get('workers', []):
            yield self._buildbot_worker_create_worker(
                worker_dir, name, password, worker_exec)

        for slave_dir, name, password, slave_exec in env.get('slaves', []):
            yield self._buildslave_create_slave(
                slave_dir, name, password, slave_exec)

        yield self._buildbot_start(master_dir)

        for worker_dir, name, password, worker_exec in env.get('workers', []):
            yield self._buildbot_worker_start(worker_dir, worker_exec)

        for slave_dir, name, password, slave_exec in env.get('slaves', []):
            yield self._buildslave_start(slave_dir, slave_exec)

    @defer.inlineCallbacks
    def teardownEnvironment(self):
        for worker_dir in list(self.running_workers.keys()):
            yield self.running_workers[worker_dir].stop()
            del self.running_workers[worker_dir]

        for slave_dir in list(self.running_slaves.keys()):
            yield self.running_slaves[slave_dir].stop()
            del self.running_slaves[slave_dir]

        if self.running_master is not None:
            yield self.running_master.stop()
            self.running_master = None
