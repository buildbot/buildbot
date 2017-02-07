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

from __future__ import print_function

import functools
import os
import re
import socket
import textwrap

try:
    from textwrap import indent
except ImportError:
    # textwrap.indent() implementation from Python 3.3
    def indent(text, prefix, predicate=None):
        """Adds 'prefix' to the beginning of selected lines in 'text'.

        If 'predicate' is provided, 'prefix' will only be added to the lines
        where 'predicate(line)' is True. If 'predicate' is not provided,
        it will default to adding 'prefix' to all non-empty lines that do not
        consist solely of whitespace characters.
        """
        if predicate is None:
            def predicate(line):  # pylint: disable=function-redefined
                return line.strip()

        def prefixed_lines():
            for line in text.splitlines(True):
                yield (prefix + line if predicate(line) else line)
        return ''.join(prefixed_lines())

from fastjsonrpc.client import Proxy
from fastjsonrpc.client import jsonrpc
from twisted.internet import reactor as global_reactor
from twisted.internet import defer
from twisted.internet import task
from twisted.internet import utils
from twisted.python import log
from twisted.trial import unittest
from txrequests import Session

from buildbot.test.util import dirs
from buildbot.test.util.decorators import skipIf
from buildbot.test.util.decorators import skipUnlessPlatformIs

try:
    from shutil import which
except ImportError:
    # Backport of shutil.which() from Python 3.3.
    from shutilwhich import which


def get_buildslave_executable():
    return which("buildslave")


def get_buildbot_executable():
    return which("buildbot")


def get_buildbot_worker_executable():
    return which("buildbot-worker")


buildslave_executable = get_buildslave_executable()
buildbot_worker_executable = get_buildbot_worker_executable()
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
        is_completed = yield is_completed_pred()

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


def record_test_failure(coro):
    @functools.wraps(coro)
    def wrapper(self):
        try:
            return coro(self)
        except Exception:
            self.success = False
            raise

    return wrapper


# TODO: Current implementation uses the fact that Buildbot processes are being
# daemonized, which is not the case on Windows.
# Implementation that uses `--nodaemon` version of Buildbot services can
# be used to run these tests on Windows.
@skipUnlessPlatformIs('posix')
class TestMasterWorkerSetup(dirs.DirsMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self._origcwd = os.getcwd()
        test_name = self.id().rsplit('.', 1)[1]
        self.projectdir = os.path.abspath('project_' + test_name)
        yield self.setUpDirs(self.projectdir)
        os.chdir(self.projectdir)

        self.master_port = get_open_port()
        self.ui_port = get_open_port()

        # Working directories of masters and workers.
        # Populated when appropriate master or workers are created.
        # Used for test cleanup in case of failure (force stop still running
        # master/worker).
        self.master_dir = None
        self.workers_dirs = []
        self.slaves_dirs = []

        self.logs = []
        self.success = True

        self.session = Session()

    @defer.inlineCallbacks
    def tearDown(self):
        if not self.success:
            self.logs.append(
                "Test failed, trying to stop possibly running services")
            yield self._force_stop()

            # Output ran command logs to stdout to help debugging in CI systems
            # where logs are not available (e.g. Travis).
            # Logs can be stored on AppVeyor and CircleCI, we can move
            # e2e tests there if we don't want such output.
            print("Test failed, output:")
            print("-" * 80)
            print("\n".join(self.logs))
            print("-" * 80)
            self._print_all_logs()

            os.chdir(self._origcwd)

        else:
            os.chdir(self._origcwd)

            # Clean working directory only when test succeeded.
            yield self.tearDownDirs()

        self.session.close()

    @defer.inlineCallbacks
    def _force_stop(self):
        """Force stop running master/workers"""

        for worker_dir in self.workers_dirs:
            try:
                yield self._run_command(
                    [buildbot_worker_executable, 'stop', worker_dir])
            except Exception:
                # Ignore errors.
                pass

        for slave_dir in self.slaves_dirs:
            try:
                yield self._run_command(
                    [buildslave_executable, 'stop', slave_dir])
            except Exception:
                # Ignore errors.
                pass

        if self.master_dir is not None:
            try:
                yield self._run_command([
                    buildbot_executable, 'stop', self.master_dir])
            except Exception:
                # Ignore errors.
                pass

    def _print_all_logs(self):
        """Print all started services Twistd logs"""

        logs = []

        if self.master_dir:
            logs.append(os.path.join(self.master_dir, "twistd.log"))
        for worker_dir in self.workers_dirs:
            logs.append(os.path.join(worker_dir, "twistd.log"))
        for slave_dir in self.slaves_dirs:
            logs.append(os.path.join(slave_dir, "twistd.log"))

        for log_path in logs:
            if os.path.exists(log_path):
                with open(log_path, "rt") as f:
                    print("Log '{}':".format(log_path))
                    print(indent(f.read(), "    "))

    def _log(self, msg):
        self.logs.append(msg)
        log.msg(msg)

    @defer.inlineCallbacks
    def _run_command(self, args):
        command_str = " ".join(args)
        self._log("Running command: '{0}'".format(command_str))

        executable, args = args[0], args[1:]

        # Find executable in path.
        executable_path = which(executable)
        if executable_path is None:
            raise RuntimeError(
                "Can't find '{0}' in path.".format(executable))

        stdout, stderr, exitcode = yield utils.getProcessOutputAndValue(
            executable_path, args)

        if stderr:
            self._log("stderr:\n{0}".format(indent(stderr, "    ")))
        if stdout:
            self._log("stdout:\n{0}".format(indent(stdout, "    ")))
        self._log("Process finished with code {0}".format(exitcode))
        assert exitcode == 0, "command failed: '{0}'".format(command_str)

        defer.returnValue((stdout, stderr))

    @defer.inlineCallbacks
    def _buildbot_create_master(self, master_dir):
        """Runs "buildbot create-master" and checks result"""
        assert self.master_dir is None
        self.master_dir = master_dir
        stdout, _ = yield self._run_command(
            [buildbot_executable, 'create-master', master_dir])
        self.assertIn("buildmaster configured in", stdout)

    @defer.inlineCallbacks
    def _buildbot_worker_create_worker(self, worker_dir, name, password):
        self.workers_dirs.append(worker_dir)
        master_addr = 'localhost:{port}'.format(port=self.master_port)
        stdout, _ = yield self._run_command([
            buildbot_worker_executable, 'create-worker', worker_dir,
            master_addr, name, password])
        self.assertIn("worker configured in", stdout)

    @defer.inlineCallbacks
    def _buildslave_create_slave(self, slave_dir, name, password):
        self.slaves_dirs.append(slave_dir)
        master_addr = 'localhost:{port}'.format(port=self.master_port)
        stdout, _ = yield self._run_command([
            buildslave_executable, 'create-slave', slave_dir,
            master_addr, name, password])
        self.assertIn("buildslave configured in", stdout)

    @defer.inlineCallbacks
    def _buildbot_start(self, master_dir):
        stdout, _ = yield self._run_command([
            buildbot_executable, 'start', master_dir])
        self.assertIn(
            "The buildmaster appears to have (re)started correctly",
            stdout)

    @defer.inlineCallbacks
    def _buildbot_stop(self, master_dir):
        stdout, _ = yield self._run_command([
            buildbot_executable, 'stop', master_dir])
        self.assertRegexpMatches(stdout, r"buildbot process \d+ is dead")

    @defer.inlineCallbacks
    def _buildbot_worker_start(self, worker_dir):
        stdout, _ = yield self._run_command([
            buildbot_worker_executable, 'start', worker_dir])

        self.assertIn(
            "The buildbot-worker appears to have (re)started correctly",
            stdout)

    @defer.inlineCallbacks
    def _buildbot_worker_stop(self, worker_dir):
        stdout, _ = yield self._run_command(
            [buildbot_worker_executable, 'stop', worker_dir])
        self.assertRegexpMatches(stdout, r"worker process \d+ is dead")

    @defer.inlineCallbacks
    def _buildslave_start(self, slave_dir):
        stdout, _ = yield self._run_command([
            buildslave_executable, 'start', slave_dir])

        self.assertIn(
            "The buildslave appears to have (re)started correctly",
            stdout)

    @defer.inlineCallbacks
    def _buildslave_stop(self, slave_dir):
        stdout, _ = yield self._run_command(
            [buildslave_executable, 'stop', slave_dir])
        self.assertRegexpMatches(stdout, r"buildslave process \d+ is dead")

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

        self.success = True

    @record_test_failure
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

    @record_test_failure
    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_shell_command_on_worker(self):
        """Run simple ShellCommand on worker."""

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Write master configuration.
        master_cfg = SHELL_COMMAND_TEST_CONFIG
        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildbot_worker_create_worker(
            worker_dir, 'example-worker', 'pass')

        # Start master/worker.
        yield self._buildbot_start(master_dir)
        yield self._buildbot_worker_start(worker_dir)

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

        # Stop master/worker.
        yield self._buildbot_worker_stop(worker_dir)
        yield self._buildbot_stop(master_dir)

    @record_test_failure
    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    def test_file_transfer_on_worker(self):
        """Run file transfer between master/worker."""

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Write master configuration.
        master_cfg = FILE_UPLOAD_TEST_CONFIG
        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildbot_worker_create_worker(
            worker_dir, 'example-worker', 'pass')

        # Start master/worker.
        yield self._buildbot_start(master_dir)
        yield self._buildbot_worker_start(worker_dir)

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

        # Stop master/worker.
        yield self._buildbot_worker_stop(worker_dir)
        yield self._buildbot_stop(master_dir)

    @record_test_failure
    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_file_transfer_on_slave(self):
        """Run file transfer between master/buildslave."""

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Write master configuration.
        master_cfg = FILE_UPLOAD_TEST_CONFIG
        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildslave_create_slave(
            worker_dir, 'example-worker', 'pass')

        # Start master/worker.
        yield self._buildbot_start(master_dir)
        yield self._buildslave_start(worker_dir)

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

        # Stop master/worker.
        yield self._buildslave_stop(worker_dir)
        yield self._buildbot_stop(master_dir)

    @record_test_failure
    @defer.inlineCallbacks
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on_slave(self):
        """Run simple ShellCommand on worker."""

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Write master configuration.
        master_cfg = SHELL_COMMAND_TEST_CONFIG
        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildslave_create_slave(
            worker_dir, 'example-worker', 'pass')

        # Start master/worker.
        yield self._buildbot_start(master_dir)
        yield self._buildslave_start(worker_dir)

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

        # Stop master/worker.
        yield self._buildslave_stop(worker_dir)
        yield self._buildbot_stop(master_dir)

    @record_test_failure
    @defer.inlineCallbacks
    @skipIf(buildbot_worker_executable is None,
            "buildbot-worker executable not found")
    @skipIf(buildslave_executable is None,
            "buildslave executable not found")
    def test_shell_command_on_worker_and_slave(self):
        """Test simultaneous work of old and new workers."""

        # Create master.
        master_dir = 'master-dir'
        yield self._buildbot_create_master(master_dir)

        # Write master configuration.
        master_cfg = WORKER_SLAVE_TEST_CONFIG
        self._write_master_config(master_dir, master_cfg)

        # Create worker.
        worker_dir = 'worker-dir'
        yield self._buildbot_worker_create_worker(
            worker_dir, 'example-worker', 'pass')

        # Create slave.
        slave_dir = 'slave-dir'
        yield self._buildslave_create_slave(
            slave_dir, 'example-slave', 'pass')

        # Start master/worker.
        yield self._buildbot_start(master_dir)
        yield self._buildbot_worker_start(worker_dir)
        yield self._buildslave_start(slave_dir)

        # Get builder ID.
        # TODO: maybe add endpoint to get builder by name?
        builders = yield self._get('builders')
        self.assertEqual(len(builders['builders']), 2)

        if builders['builders'][0]['name'] == 'worker-builder':
            worker_idx = 0
        else:
            worker_idx = 1

        worker_builder_id = builders['builders'][worker_idx]['builderid']
        slave_builder_id = builders['builders'][1 - worker_idx]['builderid']

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

        # Stop master/worker.
        yield self._buildbot_worker_stop(worker_dir)
        yield self._buildslave_stop(slave_dir)
        yield self._buildbot_stop(master_dir)
