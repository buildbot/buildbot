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


class TestDownloadSecretToWorkerStep(steps.BuildStepMixin, unittest.TestCase,
                                     configmixin.ConfigErrorsMixin):

    def createTempDir(self, dirname):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def setUp(self):
        self.temp_path = self.createTempDir("tempdir")

    def testPushSecretToWorkerStepSuccess(self):
        self.setupStep(DownloadSecretsToWorker([(os.path.join(self.temp_path, "pathA"),
         "something")]))
        self.expected_remote_commands = ""
        self.exp_result = SUCCESS
        self.runStep()

    def testPathDoesNotExists(self):
        self.assertRaises(ValueError,
                          lambda: self.setupStep(DownloadSecretsToWorker([(os.path.join("/dir/pathA"),
                                                                           "something")])))


class TestDownloadFileSecretToWorker(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        self.setupStep(
            DownloadSecretsToWorker([((os.path.join(self.temp_path, "pathA"), "something", )),
                                     ((os.path.join(self.temp_path, "pathB")), "something more")]))
        args1 = {
                    'maxsize': None,
                    'reader': ExpectRemoteRef(remotetransfer.FileReader),
                    'blocksize': 32 * 1024,
                    'workerdest': os.path.join(self.temp_path, "pathA")
                    }
        args2 = {
                    'maxsize': None,
                    'reader': ExpectRemoteRef(remotetransfer.FileReader),
                    'blocksize': 32 * 1024,
                    'workerdest': os.path.join(self.temp_path, "pathB")
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


class TestRemoveSecretToWorkerStep(steps.BuildStepMixin, unittest.TestCase,
                                   configmixin.ConfigErrorsMixin):

    def createTempDir(self, dirname):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def setUp(self):
        self.temp_path = self.createTempDir("tempdir")
        file_path = os.path.join(self.temp_path, "filename")
        with open(file_path, 'w') as filetmp:
            filetmp.write("text")
            self.fileToRemove = filetmp

    def testRemoveSecretToWorkerStepSuccess(self):
        self.setupStep(RemoveWorkerFileSecret([os.path.join(self.temp_path, "filename")]))
        self.expected_remote_commands = ""
        self.exp_result = SUCCESS
        self.runStep()


class TestRemoveFileSecretToWorkerStep(steps.BuildStepMixin, unittest.TestCase,
                                   configmixin.ConfigErrorsMixin):

    def setUp(self):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        self.temp_path = tempdir.path
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        self.setupStep(
            RemoveWorkerFileSecret([(os.path.join(self.temp_path, "pathA")),
                                    (os.path.join(self.temp_path, "pathB"))]))
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
