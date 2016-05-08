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

import os
import re
import socket

from buildbot.test.util import dirs

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import log
from twisted.trial import unittest

try:
    from shutil import which
except ImportError:
    # Backport of shutil.which() from Python 3.3.
    from shutilwhich import which


def get_open_port():
    # TODO: This is synchronous code which might be blocking, which is
    # unacceptable in Twisted.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


class TestMasterWorkerSetup(dirs.DirsMixin, unittest.TestCase):

    try:
        import buildbot_worker  # noqa pylint: disable=unused-import
    except ImportError:
        skip = "buildbot-worker package is not installed"

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

        self.logs = []
        self.success = False

    @defer.inlineCallbacks
    def tearDown(self):
        os.chdir(self._origcwd)

        if not self.success:
            yield self._force_stop()

            # Output ran command logs to stdout to help debugging in CI systems
            # where logs are not available (e.g. Travis).
            # Logs can be stored on AppVeyor and CircleCI, we can move
            # e2e tests there if we don't want such output.
            print("Test failed, output:")
            print("-" * 80)
            print("\n".join(self.logs))
            print("-" * 80)
        else:
            # Clean working directory only when test succeeded.
            yield self.tearDownDirs()

    @defer.inlineCallbacks
    def _force_stop(self):
        """Force stop running master/workers"""
        for worker_dir in self.workers_dirs:
            try:
                yield self._run_command(["buildbot-worker", "stop", worker_dir])
            except Exception:
                # Ignore errors.
                pass

        if self.master_dir is not None:
            try:
                yield self._run_command(["buildbot", "stop", self.master_dir])
            except Exception:
                # Ignore errors.
                pass

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
            self._log("stderr:\n{0}".format(stderr))
        if stdout:
            self._log("stdout:\n{0}".format(stdout))
        self._log("Process finished with code {0}".format(exitcode))
        assert exitcode == 0, "command failed: '{0}'".format(command_str)

        defer.returnValue((stdout, stderr))

    @defer.inlineCallbacks
    def _buildbot_create_master(self, master_dir):
        """Runs "buildbot create-master" and checks result"""
        assert self.master_dir is None
        self.master_dir = master_dir
        stdout, _ = yield self._run_command(
            ["buildbot", "create-master", master_dir])
        self.assertIn("buildmaster configured in", stdout)

    @defer.inlineCallbacks
    def _buildbot_worker_create_worker(self, worker_dir):
        self.workers_dirs.append(worker_dir)
        master_addr = "localhost:{port}".format(port=self.master_port)
        stdout, _ = yield self._run_command([
            "buildbot-worker", "create-worker", worker_dir, master_addr,
            "example-worker", "pass"])
        self.assertIn("worker configured in", stdout)

    @defer.inlineCallbacks
    def _buildbot_start(self, master_dir):
        stdout, _ = yield self._run_command(["buildbot", "start", master_dir])
        self.assertIn(
            "The buildmaster appears to have (re)started correctly",
            stdout)

    @defer.inlineCallbacks
    def _buildbot_stop(self, master_dir):
        stdout, _ = yield self._run_command(["buildbot", "stop", master_dir])
        self.assertRegexpMatches(stdout, r"buildbot process \d+ is dead")

    @defer.inlineCallbacks
    def _buildbot_worker_start(self, worker_dir):
        # Start worker.
        stdout, _ = yield self._run_command([
            "buildbot-worker", "start", worker_dir])

        self.assertIn(
            "The buildbot-worker appears to have (re)started correctly",
            stdout)

    @defer.inlineCallbacks
    def _buildbot_worker_stop(self, worker_dir):
        stdout, _ = yield self._run_command(
            ["buildbot-worker", "stop", worker_dir])
        self.assertRegexpMatches(stdout, r"worker process \d+ is dead")

    @defer.inlineCallbacks
    def test_master_worker_setup(self):
        """Create master and worker (with default pyflakes configuration),
        start them, stop them.
        """

        # Create master.
        master_dir = "master-dir"
        yield self._buildbot_create_master(master_dir)

        # Create master.cfg based on sample file.
        sample_config = os.path.join(master_dir, "master.cfg.sample")
        with open(sample_config, "rt") as f:
            master_cfg = f.read()

        # Disable www plugins (they are not installed on Travis).
        master_cfg = re.sub(r"plugins=dict\([^)]+\)", "plugins={}", master_cfg)

        # Substitute ports to listen.
        master_cfg = master_cfg.replace('9989', str(self.master_port))
        master_cfg = master_cfg.replace('8010', str(self.ui_port))

        with open(os.path.join(master_dir, "master.cfg"), "wt") as f:
            f.write(master_cfg)

        # Create worker.
        worker_dir = "worker-dir"
        yield self._buildbot_worker_create_worker(worker_dir)

        # Start master.
        yield self._buildbot_start(master_dir)

        # Start worker.
        yield self._buildbot_worker_start(worker_dir)

        # Stop worker.
        yield self._buildbot_worker_stop(worker_dir)

        # Stop master.
        yield self._buildbot_stop(master_dir)

        self.success = True
