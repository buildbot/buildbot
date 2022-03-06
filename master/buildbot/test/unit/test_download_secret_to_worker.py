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
import stat

from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.process import remotetransfer
from buildbot.process.results import SUCCESS
from buildbot.steps.download_secret_to_worker import DownloadSecretsToWorker
from buildbot.steps.download_secret_to_worker import RemoveWorkerFileSecret
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectRmfile
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import config as configmixin


class TestDownloadFileSecretToWorkerCommand(TestBuildStepMixin,
                                            TestReactorMixin,
                                            unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def testBasic(self):
        self.setup_step(
            DownloadSecretsToWorker([(os.path.join(self.temp_path, "pathA"), "something"),
                                     (os.path.join(self.temp_path, "pathB"), "something more")]))
        self.expect_commands(
            ExpectDownloadFile(maxsize=None, mode=stat.S_IRUSR | stat.S_IWUSR,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               blocksize=32 * 1024,
                               workerdest=os.path.join(self.temp_path, "pathA"), workdir="wkdir")
            .exit(0),
            ExpectDownloadFile(maxsize=None, mode=stat.S_IRUSR | stat.S_IWUSR,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               blocksize=32 * 1024,
                               workerdest=os.path.join(self.temp_path, "pathB"), workdir="wkdir")
            .exit(0),
            )

        self.expect_outcome(
            result=SUCCESS, state_string="finished")
        d = self.run_step()
        return d


class TestRemoveWorkerFileSecretCommand30(TestBuildStepMixin,
                                          TestReactorMixin,
                                          unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def testBasic(self):
        self.setup_step(RemoveWorkerFileSecret(
                            [(os.path.join(self.temp_path, "pathA"), "something"),
                            (os.path.join(self.temp_path, "pathB"),
                            "somethingmore")]),
                       worker_version={'*': '3.0'})

        self.expect_commands(
            ExpectRmdir(path=os.path.join(self.temp_path, "pathA"),
                        dir=os.path.abspath(os.path.join(self.temp_path, "pathA")),
                        log_environ=False)
            .exit(0),
            ExpectRmdir(path=os.path.join(self.temp_path, "pathB"),
                        dir=os.path.abspath(os.path.join(self.temp_path, "pathB")),
                        log_environ=False)
            .exit(0),
            )

        self.expect_outcome(
            result=SUCCESS, state_string="finished")
        d = self.run_step()
        return d


class TestRemoveFileSecretToWorkerCommand(TestBuildStepMixin,
                                          configmixin.ConfigErrorsMixin,
                                          TestReactorMixin,
                                          unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def testBasic(self):
        self.setup_step(
            RemoveWorkerFileSecret([(os.path.join(self.temp_path, "pathA"), "something"),
                                    (os.path.join(self.temp_path, "pathB"), "somethingmore")]))
        self.expect_commands(
            ExpectRmfile(path=os.path.join(self.temp_path, "pathA"), log_environ=False)
            .exit(0),
            ExpectRmfile(path=os.path.join(self.temp_path, "pathB"), log_environ=False)
            .exit(0),
            )

        self.expect_outcome(
            result=SUCCESS, state_string="finished")
        d = self.run_step()
        return d
