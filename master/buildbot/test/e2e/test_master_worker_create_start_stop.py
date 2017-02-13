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
import textwrap
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
from buildbot.test.util.decorators import skipIf
from buildbot.test.util.decorators import skipUnlessPlatformIs
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


SHELL_COMMAND_TEST_CONFIG = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['buildbotNetUsageData'] = None

c['workers'] = [worker.Worker('example-worker', 'pass')]
c['protocols'] = {'pb': {'port': 9989}}
c['schedulers'] = [
    schedulers.ForceScheduler(
        name='force',
        builderNames=['runtests'])
]

factory = util.BuildFactory(
    [steps.ShellCommand(command=['echo', "Test echo"])])

c['builders'] = [
    util.BuilderConfig(name='runtests', workernames=['example-worker'],
        factory=factory),
]

c['buildbotURL'] = 'http://localhost:8010/'
c['www'] = dict(port=8010, plugins={})
c['db'] = {
    'db_url' : 'sqlite:///state.sqlite',
}
"""

WORKER_SLAVE_TEST_CONFIG = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['buildbotNetUsageData'] = None

c['workers'] = [
    # worker.Worker and buildslave.BuildSlave are synonims, there is no actual
    # need to use worker.Worker for buildbot-worker instances and
    # buildslave.BuildSlave for deprecated buildslave instances.
    worker.Worker('example-worker', 'pass'),
    buildslave.BuildSlave('example-slave', 'pass'),
]
c['protocols'] = {'pb': {'port': 9989}}
c['schedulers'] = [
    schedulers.ForceScheduler(
        name='worker-force',
        builderNames=['worker-builder']),
    schedulers.ForceScheduler(
        name='slave-force',
        builderNames=['slave-builder']),
]

worker_factory = util.BuildFactory(
    [steps.ShellCommand(command=['echo', "Test worker"])])
slave_factory = util.BuildFactory(
    [steps.ShellCommand(command=['echo', "Test slave"])])

c['builders'] = [
    util.BuilderConfig(name='worker-builder', workernames=['example-worker'],
        factory=worker_factory),
    util.BuilderConfig(name='slave-builder', workernames=['example-slave'],
        factory=slave_factory),
]

c['buildbotURL'] = 'http://localhost:8010/'
c['www'] = dict(port=8010, plugins={})
c['db'] = {
    'db_url' : 'sqlite:///state.sqlite',
}
"""

FILE_UPLOAD_TEST_CONFIG = """\
from buildbot.plugins import *

c = BuildmasterConfig = {}

c['buildbotNetUsageData'] = None

c['workers'] = [worker.Worker('example-worker', 'pass')]
c['protocols'] = {'pb': {'port': 9989}}
c['schedulers'] = [
    schedulers.ForceScheduler(
        name='force',
        builderNames=['runtests'])
]

factory = util.BuildFactory()
factory.addStep(
    steps.StringDownload("filecontent", workerdest="dir/file1.txt"))
factory.addStep(
    steps.StringDownload("filecontent2", workerdest="dir/file2.txt"))
factory.addStep(
    steps.FileUpload(workersrc="dir/file2.txt", masterdest="master.txt"))
factory.addStep(
    steps.FileDownload(mastersrc="master.txt", workerdest="dir/file3.txt"))
factory.addStep(steps.DirectoryUpload(workersrc="dir", masterdest="dir"))

c['builders'] = [
    util.BuilderConfig(name='runtests', workernames=['example-worker'],
        factory=factory),
]

c['buildbotURL'] = 'http://localhost:8010/'
c['www'] = dict(port=8010, plugins={})
c['db'] = {
    'db_url' : 'sqlite:///state.sqlite',
}
"""


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


def _read_dir_contents(dirname):
    contents = {}
    for root, _, files in os.walk(dirname):
        for name in files:
            filename = os.path.join(root, name)
            with open(filename) as f:
                contents[filename] = f.read()
    return contents


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
            log.debug("Found started mark {!r}".format(started_mark))
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

            if still_running:
                raise RuntimeError(
                    "One of the started processes not stopped. "
                    "Did you forgot to call teardownEnvironment()?")

        else:
            os.chdir(self._origcwd)

            # Clean working directory only when test succeeded.
            yield self.tearDownDirs()

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


class TestMasterWorkerSetup(E2ETestBase):

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_master_worker_setup(self):
        """Create master and worker (with default pyflakes configuration),
        start them, stop them.
        """

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Create master.cfg based on sample file.
        sample_config = os.path.join(master_dir, 'master.cfg.sample')
        with open(sample_config, 'rt') as f:
            master_cfg = f.read()

        # Disable www plugins (they are not installed on Travis).
        master_cfg = re.sub(r"plugins=dict\([^)]+\)", "plugins={}", master_cfg)
        # Disable usage reporting.
        master_cfg += """\nc['buildbotNetUsageData'] = None\n"""

        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildbot_worker_create_worker(
            worker_dir, 'example-worker', 'pass')

        # Start.
        yield self._buildbot_start(master_dir)
        yield self._buildbot_worker_start(worker_dir)

        # Stop.
        yield self._buildbot_worker_stop(worker_dir)
        yield self._buildbot_stop(master_dir)

        # Check master logs.
        with open(os.path.join(master_dir, "twistd.log"), 'rt') as f:
            log = f.read()

        # Check that worker info was received without warnings.
        worker_connection_re = textwrap.dedent(
            r"""
            [^\n]+ worker 'example-worker' attaching from [^\n]+
            [^\n]+ Got workerinfo from 'example-worker'
            """)

        self.assertTrue(
            re.search(worker_connection_re, log, re.MULTILINE),
            msg="Log doesn't match:\n{0}\nLog:\n{1}".format(
                indent(worker_connection_re, "    "),
                indent(log, "    ")))

    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_master_slave_setup(self):
        """Create master and slave (with default pyflakes configuration),
        start them, stop them.
        """

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Create master.cfg based on sample file.
        sample_config = os.path.join(master_dir, 'master.cfg.sample')
        with open(sample_config, 'rt') as f:
            master_cfg = f.read()

        # Disable www plugins (they are not installed on Travis).
        master_cfg = re.sub(r"plugins=dict\([^)]+\)", "plugins={}", master_cfg)
        # Disable usage reporting.
        master_cfg += """\nc['buildbotNetUsageData'] = None\n"""

        self._write_master_config(master_dir, master_cfg)

        # Create slave.
        slave_dir = 'slave-dir'
        yield self._buildslave_create_slave(
            slave_dir, 'example-worker', 'pass')

        # Start.
        yield self._buildbot_start(master_dir)
        yield self._buildslave_start(slave_dir)

        # Stop.
        yield self._buildslave_stop(slave_dir)
        yield self._buildbot_stop(master_dir)

        # Check master logs.
        with open(os.path.join(master_dir, "twistd.log"), 'rt') as f:
            log = f.read()

        # Check that slave info was received with message about fallback from
        # buildbot-worker methods.
        worker_connection_re = textwrap.dedent(
            r"""
            [^\n]+ worker 'example-worker' attaching from [^\n]+
            [^\n]+ Worker.getWorkerInfo is unavailable - falling back [^\n]+
            [^\n]+ Got workerinfo from 'example-worker'
            """)

        self.assertTrue(
            re.search(worker_connection_re, log, re.MULTILINE),
            msg="Log doesn't match:\n{0}\nLog:\n{1}".format(
                indent(worker_connection_re, "    "),
                indent(log, "    ")))


class ShellCommandTestMixin:

    @defer.inlineCallbacks
    def run_check(self):
        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 1)
        builder_id = builders['builders'][0]['builderid']

        # Start force build.
        # TODO: return result is not documented in RAML.
        buildset_id, buildrequests_ids = yield self._call_rpc(
            'forceschedulers/force', 'force', builderid=builder_id)

        @defer.inlineCallbacks
        def is_completed():
            # Query buildset completion status.
            buildsets = yield self._get('buildsets/{0}'.format(buildset_id))
            defer.returnValue(buildsets['buildsets'][0]['complete'])

        yield wait_for_completion(is_completed)

        # TODO: Looks like there is no easy way to get build identifier that
        # corresponds to buildrequest/buildset.
        buildnumber = 1

        # Get completed build info.
        builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=builder_id, buildnumber=buildnumber))

        self.assertEqual(builds['builds'][0]['state_string'], 'finished')

        log_row = yield self._get_raw(
            'builders/{builderid}/builds/{buildnumber}/steps/0/logs/stdio/raw'.format(
                builderid=builder_id, buildnumber=buildnumber))
        self.assertIn("echo 'Test echo'", log_row)


class ShellCommandOnWorkerNoDaemonTest(E2ETestBase, ShellCommandTestMixin):

    @defer.inlineCallbacks
    def check_shell_command_on_worker(
            self,
            master_executable=None,
            worker_executable=None):
        """Run simple ShellCommand on worker."""

        yield self.setupEnvironment({
            'masters': [
                ('master-dir', SHELL_COMMAND_TEST_CONFIG, master_executable),
            ],
            'workers': [
                ('worker-dir', 'example-worker', 'pass', worker_executable),
            ],
        })

        yield self.run_check()

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_shell_command_on_worker(self):
        yield self.check_shell_command_on_worker()


@skipUnlessPlatformIs('posix')
class ShellCommandOnWorkerDaemonTest(
        ShellCommandOnWorkerNoDaemonTest, DaemonMixin):
    pass


class FileTransferTestMixin:

    @defer.inlineCallbacks
    def run_check(self, master_dir):
        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 1)
        builder_id = builders['builders'][0]['builderid']

        # Start force build.
        # TODO: return result is not documented in RAML.
        buildset_id, buildrequests_ids = yield self._call_rpc(
            'forceschedulers/force', 'force', builderid=builder_id)

        @defer.inlineCallbacks
        def is_completed():
            # Query buildset completion status.
            buildsets = yield self._get('buildsets/{0}'.format(buildset_id))
            defer.returnValue(buildsets['buildsets'][0]['complete'])

        yield wait_for_completion(is_completed)

        # TODO: Looks like there is no easy way to get build identifier that
        # corresponds to buildrequest/buildset.
        buildnumber = 1

        # Get completed build info.
        builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=builder_id, buildnumber=buildnumber))

        self.assertEqual(builds['builds'][0]['state_string'], 'finished')

        master_contents = _read_dir_contents(os.path.join(master_dir, "dir"))
        self.assertEqual(
            master_contents,
            {os.path.join(master_dir, 'dir', 'file1.txt'): 'filecontent',
             os.path.join(master_dir, 'dir', 'file2.txt'): 'filecontent2',
             os.path.join(master_dir, 'dir', 'file3.txt'): 'filecontent2'})


class FileTransferOnWorkerNoDaemonTest(E2ETestBase, FileTransferTestMixin):

    @defer.inlineCallbacks
    def check_file_transfer_on_worker(
            self,
            master_executable=None,
            worker_executable=None):
        """Run file transfer between master/worker."""

        master_dir = 'master-dir'

        yield self.setupEnvironment({
            'masters': [
                (master_dir, FILE_UPLOAD_TEST_CONFIG, master_executable),
            ],
            'workers': [
                ('worker-dir', 'example-worker', 'pass', worker_executable),
            ],
        })

        yield self.run_check(master_dir)

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_file_transfer_on_worker(self):
        yield self.check_file_transfer_on_worker()


@skipUnlessPlatformIs('posix')
class FileTransferOnWorkerDaemonTest(
        FileTransferOnWorkerNoDaemonTest, DaemonMixin):
    pass


class FileTransferOnSlaveNoDaemonTest(E2ETestBase, FileTransferTestMixin):

    @defer.inlineCallbacks
    def check_file_transfer_on_slave(
            self,
            master_executable=None,
            slave_executable=None):
        """Run file transfer between master/buildslave."""

        master_dir = 'master-dir'

        yield self.setupEnvironment({
            'masters': [
                (master_dir, FILE_UPLOAD_TEST_CONFIG, master_executable),
            ],
            'slaves': [
                ('worker-dir', 'example-worker', 'pass', slave_executable),
            ],
        })

        yield self.run_check(master_dir)

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_file_transfer_on_slave(self):
        yield self.check_file_transfer_on_slave()


@skipUnlessPlatformIs('posix')
class FileTransferOnSlaveDaemonTest(
        FileTransferOnSlaveNoDaemonTest, DaemonMixin):
    pass


class ShellCommandOnSlaveNoDaemonTest(E2ETestBase, ShellCommandTestMixin):

    @defer.inlineCallbacks
    def check_shell_command_on_slave(
            self,
            master_executable=None,
            slave_executable=None):
        """Run simple ShellCommand on slave."""

        yield self.setupEnvironment({
            'masters': [
                ('master-dir', SHELL_COMMAND_TEST_CONFIG, master_executable),
            ],
            'slaves': [
                ('worker-dir', 'example-worker', 'pass', slave_executable),
            ],
        })

        yield self.run_check()

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on__slave(self):
        yield self.check_shell_command_on_slave()


@skipUnlessPlatformIs('posix')
class ShellCommandOnSlaveDaemonTest(
        ShellCommandOnSlaveNoDaemonTest, DaemonMixin):
    pass


class ShellCommandOnWorkerAndSlaveNoDaemonTest(E2ETestBase):

    @defer.inlineCallbacks
    def check_shell_command_on_worker_and_slave(
            self,
            master_executable=None,
            worker_executable=None,
            slave_executable=None):

        yield self.setupEnvironment({
            'masters': [
                ('master-dir', WORKER_SLAVE_TEST_CONFIG, master_executable),
            ],
            'workers': [
                ('worker-dir', 'example-worker', 'pass', worker_executable),
            ],
            'slaves': [
                ('slave-dir', 'example-slave', 'pass', slave_executable),
            ]
        })

        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 2)

        if builders['builders'][0]['name'] == 'worker-builder':
            worker_idx = 0
            slave_idx = 1
        else:
            worker_idx = 1
            slave_idx = 0

        worker_builder_id = builders['builders'][worker_idx]['builderid']
        slave_builder_id = builders['builders'][slave_idx]['builderid']

        # Start worker force build.
        worker_buildset_id, worker_buildrequests_ids = yield self._call_rpc(
            'forceschedulers/worker-force', 'force',
            builderid=worker_builder_id)

        # Start slave force build.
        slave_buildset_id, slave_buildrequests_ids = yield self._call_rpc(
            'forceschedulers/slave-force', 'force',
            builderid=slave_builder_id)

        @defer.inlineCallbacks
        def is_builds_completed():
            # Query buildset completion status.
            worker_buildsets = yield self._get(
                'buildsets/{0}'.format(worker_buildset_id))
            slave_buildsets = yield self._get(
                'buildsets/{0}'.format(slave_buildset_id))

            worker_complete = worker_buildsets['buildsets'][0]['complete']
            slave_complete = slave_buildsets['buildsets'][0]['complete']

            defer.returnValue(worker_complete and slave_complete)

        yield wait_for_completion(is_builds_completed)

        # TODO: Looks like there is no easy way to get build identifier that
        # corresponds to buildrequest/buildset.
        buildnumber = 1

        # Get worker completed build info.
        worker_builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=worker_builder_id, buildnumber=buildnumber))

        self.assertEqual(
            worker_builds['builds'][0]['state_string'], 'finished')

        log_row = yield self._get_raw(
            'builders/{builderid}/builds/{buildnumber}/'
            'steps/0/logs/stdio/raw'.format(
                builderid=worker_builder_id, buildnumber=buildnumber))
        self.assertIn("echo 'Test worker'", log_row)

        # Get slave completed build info.
        slave_builds = yield self._get(
            'builders/{builderid}/builds/{buildnumber}'.format(
                builderid=slave_builder_id, buildnumber=buildnumber))

        self.assertEqual(
            slave_builds['builds'][0]['state_string'], 'finished')

        log_row = yield self._get_raw(
            'builders/{builderid}/builds/{buildnumber}/'
            'steps/0/logs/stdio/raw'.format(
                builderid=slave_builder_id, buildnumber=buildnumber))
        self.assertIn("echo 'Test slave'", log_row)

        yield self.teardownEnvironment()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on_worker_and_slave(self):
        yield self.check_shell_command_on_worker_and_slave()

    @defer.inlineCallbacks
    @skipIf(buildbot_worker_py3_executable is None,
            "buildbot-worker on Python 3 is not specified")
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on_worker_py3_and_slave(self):
        yield self.check_shell_command_on_worker_and_slave(
            buildbot_worker_executable=buildbot_worker_py3_executable)


@skipUnlessPlatformIs('posix')
class ShellCommandOnWorkerAndSlaveDaemonTest(
        ShellCommandOnWorkerAndSlaveNoDaemonTest, DaemonMixin):
    pass
