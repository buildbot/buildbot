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
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.util import config as configmixin
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin


class TestDownloadFileSecretToWorkerCommand(steps.BuildStepMixin,
                                            TestReactorMixin,
                                            unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        self.setupStep(
            DownloadSecretsToWorker([(os.path.join(self.temp_path, "pathA"), "something"),
                                     (os.path.join(self.temp_path, "pathB"), "something more")]))
        args1 = {
                    'maxsize': None,
                    'mode': stat.S_IRUSR | stat.S_IWUSR,
                    'reader': ExpectRemoteRef(remotetransfer.StringFileReader),
                    'blocksize': 32 * 1024,
                    'workerdest': os.path.join(self.temp_path, "pathA"),
                    'workdir': "wkdir"
                    }
        args2 = {
                    'maxsize': None,
                    'mode': stat.S_IRUSR | stat.S_IWUSR,
                    'reader': ExpectRemoteRef(remotetransfer.StringFileReader),
                    'blocksize': 32 * 1024,
                    'workerdest': os.path.join(self.temp_path, "pathB"),
                    'workdir': "wkdir"
                    }
        self.expectCommands(
            Expect('downloadFile', args1)
            + 0,
            Expect('downloadFile', args2)
            + 0,
            )

        self.expectOutcome(
            result=SUCCESS, state_string="finished")
        d = self.runStep()
        return d


class TestRemoveWorkerFileSecretCommand30(steps.BuildStepMixin,
                                          TestReactorMixin,
                                          unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        self.setupStep(RemoveWorkerFileSecret([(os.path.join(self.temp_path, "pathA"), "something"),
                                               (os.path.join(self.temp_path, "pathB"),
                                                "somethingmore")]),
                       worker_version={'*': '3.0'})

        args1 = {
                    'path': os.path.join(self.temp_path, "pathA"),
                    'dir': os.path.abspath(os.path.join(self.temp_path, "pathA")),
                    'logEnviron': False
                    }
        args2 = {
                    'path': os.path.join(self.temp_path, "pathB"),
                    'dir': os.path.abspath(os.path.join(self.temp_path, "pathB")),
                    'logEnviron': False
                    }
        self.expectCommands(
            Expect('rmdir', args1)
            + 0,
            Expect('rmdir', args2)
            + 0,
            )

        self.expectOutcome(
            result=SUCCESS, state_string="finished")
        d = self.runStep()
        return d


class TestRemoveFileSecretToWorkerCommand(steps.BuildStepMixin,
                                          configmixin.ConfigErrorsMixin,
                                          TestReactorMixin,
                                          unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        self.setupStep(
            RemoveWorkerFileSecret([(os.path.join(self.temp_path, "pathA"), "something"),
                                    (os.path.join(self.temp_path, "pathB"), "somethingmore")]))
        args1 = {
                    'path': os.path.join(self.temp_path, "pathA"),
                    'logEnviron': False
                    }
        args2 = {
                    'path': os.path.join(self.temp_path, "pathB"),
                    'logEnviron': False
                    }
        self.expectCommands(
            Expect('rmfile', args1)
            + 0,
            Expect('rmfile', args2)
            + 0,
            )

        self.expectOutcome(
            result=SUCCESS, state_string="finished")
        d = self.runStep()
        return d
