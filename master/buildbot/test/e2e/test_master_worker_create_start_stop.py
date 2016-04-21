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
import subprocess

from twisted.internet import defer
from twisted.python import log
from twisted.trial import unittest

from buildbot.test.util import dirs


class TestMasterWorkerSetup(dirs.DirsMixin, unittest.TestCase):

    try:
        import buildbot_worker as _  # noqa pylint: disable=unused-import
    except ImportError:
        skip = "buildbot-worker package is not installed"

    @defer.inlineCallbacks
    def setUp(self):
        self.origcwd = os.getcwd()
        self.projectdir = os.path.abspath('project')
        yield self.setUpDirs(self.projectdir)

        self.logs = []
        self.success = False

    @defer.inlineCallbacks
    def tearDown(self):
        if not self.success:
            # Output ran command logs to stdout to help debugging in CI systems
            # where logs are not available (e.g. Travis).
            # Logs can be stored on AppVeyor and CircleCI, we can move
            # e2e tests there if we don't want such output.
            print("Test failed, output:")
            print("-" * 80)
            print("\n".join(self.logs))
            print("-" * 80)

        os.chdir(self.origcwd)
        yield self.tearDownDirs()

    def _log(self, msg):
        self.logs.append(msg)
        log.msg(msg)

    def _run_command(self, args):
        self._log("Running command: '{0}'".format(" ".join(args)))
        process = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if stderr:
            self._log("stderr:\n{0}".format(stderr))
        if stdout:
            self._log("stdout:\n{0}".format(stdout))
        self._log("Process finished with code {0}".format(process.returncode))
        return stdout, stderr

    def test_master_worker_setup(self):
        os.chdir(self.projectdir)

        master_dir = "master-dir"
        worker_dir = "worker-dir"

        # Create master.
        stdout = self._run_command(
            ["buildbot", "create-master", master_dir])[0]
        self.assertIn("buildmaster configured in", stdout)

        # Copy master.cfg with disabling www plugins (they are not installed
        # on Travis).
        with open(os.path.join(master_dir, "master.cfg.sample"), "rt") as f:
            master_cfg = f.read()
        master_cfg = re.sub(r"plugins=dict\([^)]+\)", "plugins={}", master_cfg)
        with open(os.path.join(master_dir, "master.cfg"), "wt") as f:
            f.write(master_cfg)

        # Create worker.
        stdout = self._run_command([
            "buildbot-worker", "create-worker", worker_dir, "localhost",
            "example-worker", "pass"])[0]
        self.assertIn("worker configured in", stdout)

        try:
            # Start master.
            stdout = self._run_command([
                "buildbot", "start", master_dir])[0]
            self.assertIn(
                "The buildmaster appears to have (re)started correctly",
                stdout)

            try:
                # Start worker.
                stdout = self._run_command([
                    "buildbot-worker", "start", worker_dir])[0]
                self.assertIn(
                    "The buildbot-worker appears to have (re)started "
                    "correctly",
                    stdout)

            finally:
                # Stop worker.
                stdout = self._run_command([
                    "buildbot-worker", "stop", worker_dir])[0]
                self.assertRegexpMatches(stdout, r"worker process \d+ is dead")

        finally:
            # Stop master.
            stdout = self._run_command([
                "buildbot", "stop", master_dir])[0]
            self.assertRegexpMatches(stdout, r"buildbot process \d+ is dead")

        self.success = True
