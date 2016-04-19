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
import shutil
import subprocess

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util import dirs
from buildbot.test.util import misc


class TestMasterWorkerSetup(dirs.DirsMixin, unittest.TestCase):

    try:
        import buildbot_worker as _  # noqa
    except ImportError:
        skip = "buildbot-worker package is not installed"

    @defer.inlineCallbacks
    def setUp(self):
        self.origcwd = os.getcwd()
        self.projectdir = os.path.abspath('project')
        yield self.setUpDirs(self.projectdir)

    @defer.inlineCallbacks
    def tearDown(self):
        os.chdir(self.origcwd)
        yield self.tearDownDirs()

    def test_master_worker_setup(self):
        os.chdir(self.projectdir)

        master_dir = "master-dir"
        worker_dir = "worker-dir"

        # Create master.
        stdout = subprocess.check_output(
            ["buildbot", "create-master", master_dir])
        self.assertIn("buildmaster configured in", stdout)

        # Create master.cfg.
        shutil.copy(
            os.path.join(master_dir, "master.cfg.sample"),
            os.path.join(master_dir, "master.cfg"))

        # Create worker.
        stdout = subprocess.check_output([
            "buildbot-worker", "create-worker", worker_dir, "localhost",
            "example-worker", "pass"])
        self.assertIn("worker configured in", stdout)

        # Start master.
        stdout = subprocess.check_output([
            "buildbot", "start", master_dir])
        try:
            self.assertIn(
                "The buildmaster appears to have (re)started correctly",
                stdout)

            # Start worker.
            stdout = subprocess.check_output([
                "buildbot-worker", "start", worker_dir])
            try:
                self.assertIn(
                    "The buildbot-worker appears to have (re)started "
                    "correctly",
                    stdout)

            finally:
                # Stop worker.
                stdout = subprocess.check_output([
                    "buildbot-worker", "stop", worker_dir])
                self.assertRegexpMatches(stdout, r"worker process \d+ is dead")

        finally:
            # Stop master.
            stdout = subprocess.check_output([
                "buildbot", "stop", master_dir])
            self.assertIn("sent SIGTERM to process", stdout)
