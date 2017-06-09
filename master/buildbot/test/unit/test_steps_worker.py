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

import stat

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.interfaces import WorkerTooOldError
from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.process import remotetransfer
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import worker
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.util import steps
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


def uploadString(string):
    def behavior(command):
        writer = command.args['writer']
        writer.remote_write(string)
        writer.remote_close()
    return behavior


class TestSetPropertiesFromEnv(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_simple(self):
        self.setupStep(worker.SetPropertiesFromEnv(
            variables=["one", "two", "three", "five", "six"],
            source="me"))
        self.worker.worker_environ = {
            "one": "1", "two": None, "six": "6", "FIVE": "555"}
        self.worker.worker_system = 'linux'
        self.properties.setProperty("four", 4, "them")
        self.properties.setProperty("five", 5, "them")
        self.properties.setProperty("six", 99, "them")
        self.expectOutcome(result=SUCCESS,
                           state_string="Set")
        self.expectProperty('one', "1", source='me')
        self.expectNoProperty('two')
        self.expectNoProperty('three')
        self.expectProperty('four', 4, source='them')
        self.expectProperty('five', 5, source='them')
        self.expectProperty('six', '6', source='me')
        self.expectLogfile("properties",
                           "one = '1'\nsix = '6'")
        return self.runStep()

    def test_case_folding(self):
        self.setupStep(worker.SetPropertiesFromEnv(
            variables=["eNv"], source="me"))
        self.worker.worker_environ = {"ENV": 'EE'}
        self.worker.worker_system = 'win32'
        self.expectOutcome(result=SUCCESS,
                           state_string="Set")
        self.expectProperty('eNv', 'EE', source='me')
        self.expectLogfile("properties",
                           "eNv = 'EE'")
        return self.runStep()


class TestFileExists(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_found(self):
        self.setupStep(worker.FileExists(file="x"))
        self.expectCommands(
            Expect('stat', {'file': 'x'})
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="File found.")
        return self.runStep()

    def test_not_found(self):
        self.setupStep(worker.FileExists(file="x"))
        self.expectCommands(
            Expect('stat', {'file': 'x'})
            + Expect.update('stat', [0, 99, 99])
            + 0
        )
        self.expectOutcome(result=FAILURE,
                           state_string="Not a file. (failure)")
        return self.runStep()

    def test_failure(self):
        self.setupStep(worker.FileExists(file="x"))
        self.expectCommands(
            Expect('stat', {'file': 'x'})
            + 1
        )
        self.expectOutcome(result=FAILURE,
                           state_string="File not found. (failure)")
        return self.runStep()

    def test_render(self):
        self.setupStep(worker.FileExists(file=properties.Property("x")))
        self.properties.setProperty('x', 'XXX', 'here')
        self.expectCommands(
            Expect('stat', {'file': 'XXX'})
            + 1
        )
        self.expectOutcome(result=FAILURE,
                           state_string="File not found. (failure)")
        return self.runStep()

    @defer.inlineCallbacks
    def test_old_version(self):
        self.setupStep(worker.FileExists(file="x"),
                       worker_version=dict())
        self.expectOutcome(result=EXCEPTION,
                           state_string="finished (exception)")
        yield self.runStep()
        self.flushLoggedErrors(WorkerTooOldError)


class TestCopyDirectory(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(worker.CopyDirectory(src="s", dest="d"))
        self.expectCommands(
            Expect('cpdir', {'fromdir': 's', 'todir': 'd'})
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="Copied s to d")
        return self.runStep()

    def test_timeout(self):
        self.setupStep(worker.CopyDirectory(src="s", dest="d", timeout=300))
        self.expectCommands(
            Expect('cpdir', {'fromdir': 's', 'todir': 'd', 'timeout': 300})
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="Copied s to d")
        return self.runStep()

    def test_maxTime(self):
        self.setupStep(worker.CopyDirectory(src="s", dest="d", maxTime=10))
        self.expectCommands(
            Expect('cpdir', {'fromdir': 's', 'todir': 'd', 'maxTime': 10})
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="Copied s to d")
        return self.runStep()

    def test_failure(self):
        self.setupStep(worker.CopyDirectory(src="s", dest="d"))
        self.expectCommands(
            Expect('cpdir', {'fromdir': 's', 'todir': 'd'})
            + 1
        )
        self.expectOutcome(result=FAILURE,
                           state_string="Copying s to d failed.")
        return self.runStep()

    def test_render(self):
        self.setupStep(worker.CopyDirectory(
            src=properties.Property("x"), dest=properties.Property("y")))
        self.properties.setProperty('x', 'XXX', 'here')
        self.properties.setProperty('y', 'YYY', 'here')
        self.expectCommands(
            Expect('cpdir', {'fromdir': 'XXX', 'todir': 'YYY'})
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="Copied XXX to YYY")
        return self.runStep()


class TestRemoveDirectory(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(worker.RemoveDirectory(dir="d"))
        self.expectCommands(
            Expect('rmdir', {'dir': 'd'})
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                           state_string="Deleted")
        return self.runStep()

    def test_failure(self):
        self.setupStep(worker.RemoveDirectory(dir="d"))
        self.expectCommands(
            Expect('rmdir', {'dir': 'd'})
            + 1
        )
        self.expectOutcome(result=FAILURE,
                           state_string="Deleted (failure)")
        return self.runStep()

    def test_render(self):
        self.setupStep(worker.RemoveDirectory(dir=properties.Property("x")))
        self.properties.setProperty('x', 'XXX', 'here')
        self.expectCommands(
            Expect('rmdir', {'dir': 'XXX'})
            + 0
        )
        self.expectOutcome(result=SUCCESS,
                           state_string="Deleted")
        return self.runStep()


class TestMakeDirectory(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(worker.MakeDirectory(dir="d"))
        self.expectCommands(
            Expect('mkdir', {'dir': 'd'})
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="Created")
        return self.runStep()

    def test_failure(self):
        self.setupStep(worker.MakeDirectory(dir="d"))
        self.expectCommands(
            Expect('mkdir', {'dir': 'd'})
            + 1
        )
        self.expectOutcome(result=FAILURE, state_string="Created (failure)")
        return self.runStep()

    def test_render(self):
        self.setupStep(worker.MakeDirectory(dir=properties.Property("x")))
        self.properties.setProperty('x', 'XXX', 'here')
        self.expectCommands(
            Expect('mkdir', {'dir': 'XXX'})
            + 0
        )
        self.expectOutcome(result=SUCCESS, state_string="Created")
        return self.runStep()


class CompositeUser(buildstep.LoggingBuildStep, worker.CompositeStepMixin):

    def __init__(self, payload):
        self.payload = payload
        self.logEnviron = False
        buildstep.LoggingBuildStep.__init__(self)

    def start(self):
        self.addLogForRemoteCommands('stdio')
        d = self.payload(self)
        d.addCallback(self.payloadComplete)
        d.addErrback(self.failed)

    def payloadComplete(self, res):
        self.finished(FAILURE if res else SUCCESS)


class TestCompositeStepMixin(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_runRemoteCommand(self):
        cmd_args = ('foo', {'bar': False})

        def testFunc(x):
            x.runRemoteCommand(*cmd_args)
        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(Expect(*cmd_args) + 0)
        self.expectOutcome(result=SUCCESS)

    def test_runRemoteCommandFail(self):
        cmd_args = ('foo', {'bar': False})

        @defer.inlineCallbacks
        def testFunc(x):
            yield x.runRemoteCommand(*cmd_args)
        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(Expect(*cmd_args) + 1)
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    @defer.inlineCallbacks
    def test_runRemoteCommandFailNoAbandon(self):
        cmd_args = ('foo', {'bar': False})

        @defer.inlineCallbacks
        def testFunc(x):
            yield x.runRemoteCommand(*cmd_args,
                                     **dict(abandonOnFailure=False))
            testFunc.ran = True
        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(Expect(*cmd_args) + 1)
        self.expectOutcome(result=SUCCESS)
        yield self.runStep()
        self.assertTrue(testFunc.ran)

    def test_rmfile(self):
        self.setupStep(CompositeUser(lambda x: x.runRmFile("d")))
        self.expectCommands(
            Expect('rmfile', {'path': 'd', 'logEnviron': False})
            + 0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mkdir(self):
        self.setupStep(CompositeUser(lambda x: x.runMkdir("d")))
        self.expectCommands(
            Expect('mkdir', {'dir': 'd', 'logEnviron': False})
            + 0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_rmdir(self):
        self.setupStep(CompositeUser(lambda x: x.runRmdir("d")))
        self.expectCommands(
            Expect('rmdir', {'dir': 'd', 'logEnviron': False})
            + 0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mkdir_fail(self):
        self.setupStep(CompositeUser(lambda x: x.runMkdir("d")))
        self.expectCommands(
            Expect('mkdir', {'dir': 'd', 'logEnviron': False})
            + 1
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_glob(self):
        @defer.inlineCallbacks
        def testFunc(x):
            res = yield x.runGlob("*.pyc")
            self.assertEqual(res, ["one.pyc", "two.pyc"])

        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(
            Expect('glob', {'path': '*.pyc', 'logEnviron': False})
            + Expect.update('files', ["one.pyc", "two.pyc"])
            + 0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_glob_fail(self):
        self.setupStep(CompositeUser(lambda x: x.runGlob("*.pyc")))
        self.expectCommands(
            Expect('glob', {'path': '*.pyc', 'logEnviron': False})
            + 1
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_abandonOnFailure(self):
        @defer.inlineCallbacks
        def testFunc(x):
            yield x.runMkdir("d")
            yield x.runMkdir("d")
        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(
            Expect('mkdir', {'dir': 'd', 'logEnviron': False})
            + 1
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_notAbandonOnFailure(self):
        @defer.inlineCallbacks
        def testFunc(x):
            yield x.runMkdir("d", abandonOnFailure=False)
            yield x.runMkdir("d", abandonOnFailure=False)
        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(
            Expect('mkdir', {'dir': 'd', 'logEnviron': False})
            + 1,
            Expect('mkdir', {'dir': 'd', 'logEnviron': False})
            + 1
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_getFileContentFromWorker(self):
        @defer.inlineCallbacks
        def testFunc(x):
            res = yield x.getFileContentFromWorker("file.txt")
            self.assertEqual(res, "Hello world!")

        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc="file.txt", workdir='wkdir',
                blocksize=32 * 1024, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.StringFileWriter))) +
            Expect.behavior(uploadString("Hello world!")) +
            0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_getFileContentFromWorker2_16(self):
        @defer.inlineCallbacks
        def testFunc(x):
            res = yield x.getFileContentFromWorker("file.txt")
            self.assertEqual(res, "Hello world!")

        self.setupStep(
            CompositeUser(testFunc),
            worker_version={'*': '2.16'})
        self.expectCommands(
            Expect('uploadFile', dict(
                slavesrc="file.txt", workdir='wkdir',
                blocksize=32 * 1024, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.StringFileWriter))) +
            Expect.behavior(uploadString("Hello world!")) +
            0
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_getFileContentFromWorker_old_api(self):
        method = mock.Mock(return_value='dummy')
        with mock.patch(
                'buildbot.steps.worker.CompositeStepMixin.getFileContentFromWorker',
                method):
            m = worker.CompositeStepMixin()
            with assertProducesWarning(
                    DeprecatedWorkerNameWarning,
                    message_pattern="'getFileContentFromSlave' method is deprecated"):
                dummy = m.getFileContentFromSlave('file')
        self.assertEqual(dummy, 'dummy')
        method.assert_called_once_with('file')

    def test_downloadFileContentToWorker(self):
        @defer.inlineCallbacks
        def testFunc(x):
            res = yield x.downloadFileContentToWorker("/path/dest1", "file text")
            self.assertEqual(res, None)

        exp_args = {'maxsize': None,
                    'reader': ExpectRemoteRef(remotetransfer.FileReader),
                    'blocksize': 32768,
                    'workerdest': '/path/dest1'}

        self.setupStep(CompositeUser(testFunc))
        self.expectCommands(
            Expect('downloadFile', exp_args)
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()


class TestWorkerTransition(unittest.TestCase):

    def test_SlaveBuildStep_deprecated(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="SlaveBuildStep was deprecated"):
            from buildbot.steps.slave import SlaveBuildStep

        self.assertIdentical(SlaveBuildStep, worker.WorkerBuildStep)
