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

from buildbot.process.results import SUCCESS
from buildbot.steps.push_secret_to_worker import PushSecretToWorker
from buildbot.steps.push_secret_to_worker import RemoveWorkerFileSecret
from buildbot.test.util import config as configmixin
from buildbot.test.util import steps


class TestPushSecretToWorkerStep(steps.BuildStepMixin, unittest.TestCase, configmixin.ConfigErrorsMixin):

    def createTempDir(self, dirname):
        tempdir = FilePath(self.mktemp())
        tempdir.createDirectory()
        return tempdir.path

    def setUp(self):
        self.temp_path = self.createTempDir("tempdir")

    def testPushSecretToWorkerStepSuccess(self):
        self.setupStep(PushSecretToWorker([(os.path.join(self.temp_path, "pathA"), "something")]))
        self.expected_remote_commands = ""
        self.exp_result = SUCCESS
        self.runStep()

    def testPathDoesNotExists(self):
        self.assertRaises(ValueError,
                          lambda: self.setupStep(PushSecretToWorker([(os.path.join("/dir/pathA"),
                                                                    "something")])))


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
