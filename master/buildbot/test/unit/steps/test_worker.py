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

from __future__ import annotations

import stat
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.process import remotetransfer
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import worker
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import Expect
from buildbot.test.steps import ExpectCpdir
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectGlob
from buildbot.test.steps import ExpectMkdir
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectRmfile
from buildbot.test.steps import ExpectStat
from buildbot.test.steps import ExpectUploadFile
from buildbot.test.steps import TestBuildStepMixin

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


class TestSetPropertiesFromEnv(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_simple(self) -> defer.Deferred[None]:
        self.setup_step(
            worker.SetPropertiesFromEnv(
                variables=["one", "two", "three", "five", "six"], source="me"
            )
        )
        self.worker.worker_environ = {"one": "1", "two": None, "six": "6", "FIVE": "555"}  # type: ignore[attr-defined]
        self.worker.worker_system = 'linux'
        self.build.setProperty("four", 4, "them")
        self.build.setProperty("five", 5, "them")
        self.build.setProperty("six", 99, "them")
        self.expect_outcome(result=SUCCESS, state_string="Set")
        self.expect_property('one', "1", source='me')
        self.expect_no_property('two')
        self.expect_no_property('three')
        self.expect_property('four', 4, source='them')
        self.expect_property('five', 5, source='them')
        self.expect_property('six', '6', source='me')
        self.expect_log_file("properties", "one = '1'\nsix = '6'")
        return self.run_step()

    def test_case_folding(self) -> defer.Deferred[None]:
        self.setup_step(worker.SetPropertiesFromEnv(variables=["eNv"], source="me"))
        self.worker.worker_environ = {"ENV": 'EE'}  # type: ignore[attr-defined]
        self.worker.worker_system = 'nt'
        self.expect_outcome(result=SUCCESS, state_string="Set")
        self.expect_property('eNv', 'EE', source='me')
        self.expect_log_file("properties", "eNv = 'EE'")
        return self.run_step()


class TestFileExists(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_found(self) -> defer.Deferred[None]:
        self.setup_step(worker.FileExists(file="x"))
        self.expect_commands(ExpectStat(file='x').stat_file().exit(0))
        self.expect_outcome(result=SUCCESS, state_string="File found.")
        return self.run_step()

    def test_not_found(self) -> defer.Deferred[None]:
        self.setup_step(worker.FileExists(file="x"))
        self.expect_commands(ExpectStat(file='x').stat(mode=0).exit(0))
        self.expect_outcome(result=FAILURE, state_string="Not a file. (failure)")
        return self.run_step()

    def test_failure(self) -> defer.Deferred[None]:
        self.setup_step(worker.FileExists(file="x"))
        self.expect_commands(ExpectStat(file='x').exit(1))
        self.expect_outcome(result=FAILURE, state_string="File not found. (failure)")
        return self.run_step()

    def test_render(self) -> defer.Deferred[None]:
        self.setup_step(worker.FileExists(file=properties.Property("x")))  # type: ignore[arg-type]
        self.build.setProperty('x', 'XXX', 'here')
        self.expect_commands(ExpectStat(file='XXX').exit(1))
        self.expect_outcome(result=FAILURE, state_string="File not found. (failure)")
        return self.run_step()

    @defer.inlineCallbacks
    def test_old_version(self) -> InlineCallbacksType[None]:
        self.setup_build(worker_version={})
        self.setup_step(worker.FileExists(file="x"))
        self.expect_outcome(result=EXCEPTION, state_string="finished (exception)")
        yield self.run_step()
        self.flushLoggedErrors(WorkerSetupError)


class TestCopyDirectory(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_success(self) -> defer.Deferred[None]:
        self.setup_step(worker.CopyDirectory(src="s", dest="d"))
        self.expect_commands(ExpectCpdir(fromdir='s', todir='d', timeout=120).exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Copied s to d")
        return self.run_step()

    def test_timeout(self) -> defer.Deferred[None]:
        self.setup_step(worker.CopyDirectory(src="s", dest="d", timeout=300))
        self.expect_commands(ExpectCpdir(fromdir='s', todir='d', timeout=300).exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Copied s to d")
        return self.run_step()

    def test_maxTime(self) -> defer.Deferred[None]:
        self.setup_step(worker.CopyDirectory(src="s", dest="d", maxTime=10))
        self.expect_commands(ExpectCpdir(fromdir='s', todir='d', max_time=10, timeout=120).exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Copied s to d")
        return self.run_step()

    def test_failure(self) -> defer.Deferred[None]:
        self.setup_step(worker.CopyDirectory(src="s", dest="d"))
        self.expect_commands(ExpectCpdir(fromdir='s', todir='d', timeout=120).exit(1))
        self.expect_outcome(result=FAILURE, state_string="Copying s to d failed. (failure)")
        return self.run_step()

    def test_render(self) -> defer.Deferred[None]:
        self.setup_step(
            worker.CopyDirectory(src=properties.Property("x"), dest=properties.Property("y"))  # type: ignore[arg-type]
        )
        self.build.setProperty('x', 'XXX', 'here')
        self.build.setProperty('y', 'YYY', 'here')
        self.expect_commands(ExpectCpdir(fromdir='XXX', todir='YYY', timeout=120).exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Copied XXX to YYY")
        return self.run_step()


class TestRemoveDirectory(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_success(self) -> defer.Deferred[None]:
        self.setup_step(worker.RemoveDirectory(dir="d"))
        self.expect_commands(ExpectRmdir(dir='d').exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Deleted")
        return self.run_step()

    def test_failure(self) -> defer.Deferred[None]:
        self.setup_step(worker.RemoveDirectory(dir="d"))
        self.expect_commands(ExpectRmdir(dir='d').exit(1))
        self.expect_outcome(result=FAILURE, state_string="Delete failed. (failure)")
        return self.run_step()

    def test_render(self) -> defer.Deferred[None]:
        self.setup_step(worker.RemoveDirectory(dir=properties.Property("x")))  # type: ignore[arg-type]
        self.build.setProperty('x', 'XXX', 'here')
        self.expect_commands(ExpectRmdir(dir='XXX').exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Deleted")
        return self.run_step()


class TestMakeDirectory(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_success(self) -> defer.Deferred[None]:
        self.setup_step(worker.MakeDirectory(dir="d"))
        self.expect_commands(ExpectMkdir(dir='d').exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Created")
        return self.run_step()

    def test_failure(self) -> defer.Deferred[None]:
        self.setup_step(worker.MakeDirectory(dir="d"))
        self.expect_commands(ExpectMkdir(dir='d').exit(1))
        self.expect_outcome(result=FAILURE, state_string="Create failed. (failure)")
        return self.run_step()

    def test_render(self) -> defer.Deferred[None]:
        self.setup_step(worker.MakeDirectory(dir=properties.Property("x")))  # type: ignore[arg-type]
        self.build.setProperty('x', 'XXX', 'here')
        self.expect_commands(ExpectMkdir(dir='XXX').exit(0))
        self.expect_outcome(result=SUCCESS, state_string="Created")
        return self.run_step()


class CompositeUser(buildstep.BuildStep, worker.CompositeStepMixin):
    def __init__(self, payload: Callable[[Any], Any]) -> None:
        self.payload = payload
        self.logEnviron = False
        super().__init__()

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        yield self.addLogForRemoteCommands('stdio')
        res = yield self.payload(self)
        return FAILURE if res else SUCCESS


class TestCompositeStepMixin(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_runRemoteCommand(self) -> None:
        cmd_args = ('foo', {'bar': False})

        def testFunc(x: Any) -> None:
            x.runRemoteCommand(*cmd_args)

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(Expect(*cmd_args).exit(0))
        self.expect_outcome(result=SUCCESS)

    def test_runRemoteCommandFail(self) -> defer.Deferred[None]:
        cmd_args = ('foo', {'bar': False})

        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            yield x.runRemoteCommand(*cmd_args)

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(Expect(*cmd_args).exit(1))
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    @defer.inlineCallbacks
    def test_runRemoteCommandFailNoAbandon(self) -> InlineCallbacksType[None]:
        cmd_args = ('foo', {'bar': False})

        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            yield x.runRemoteCommand(*cmd_args, **{"abandonOnFailure": False})
            testFunc.ran = True  # type: ignore[attr-defined]

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(Expect(*cmd_args).exit(1))
        self.expect_outcome(result=SUCCESS)
        yield self.run_step()
        self.assertTrue(testFunc.ran)  # type: ignore[attr-defined]

    def test_rmfile(self) -> defer.Deferred[None]:
        self.setup_step(CompositeUser(lambda x: x.runRmFile("d")))
        self.expect_commands(ExpectRmfile(path='d', log_environ=False).exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mkdir(self) -> defer.Deferred[None]:
        self.setup_step(CompositeUser(lambda x: x.runMkdir("d")))
        self.expect_commands(ExpectMkdir(dir='d', log_environ=False).exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_rmdir(self) -> defer.Deferred[None]:
        self.setup_step(CompositeUser(lambda x: x.runRmdir("d")))
        self.expect_commands(ExpectRmdir(dir='d', log_environ=False).exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mkdir_fail(self) -> defer.Deferred[None]:
        self.setup_step(CompositeUser(lambda x: x.runMkdir("d")))
        self.expect_commands(ExpectMkdir(dir='d', log_environ=False).exit(1))
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_glob(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            res = yield x.runGlob("*.pyc")
            self.assertEqual(res, ["one.pyc", "two.pyc"])

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(
            ExpectGlob(path='*.pyc', log_environ=False).files(["one.pyc", "two.pyc"]).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_glob_fail(self) -> defer.Deferred[None]:
        self.setup_step(CompositeUser(lambda x: x.runGlob("*.pyc")))
        self.expect_commands(ExpectGlob(path='*.pyc', log_environ=False).exit(1))
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_abandonOnFailure(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            yield x.runMkdir("d")
            yield x.runMkdir("d")

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(ExpectMkdir(dir='d', log_environ=False).exit(1))
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_notAbandonOnFailure(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            yield x.runMkdir("d", abandonOnFailure=False)
            yield x.runMkdir("d", abandonOnFailure=False)

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(
            ExpectMkdir(dir='d', log_environ=False).exit(1),
            ExpectMkdir(dir='d', log_environ=False).exit(1),
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_getFileContentFromWorker(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            res = yield x.getFileContentFromWorker("file.txt")
            self.assertEqual(res, "Hello world!")

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(
            ExpectUploadFile(
                workersrc="file.txt",
                workdir='wkdir',
                blocksize=32 * 1024,
                maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.StringFileWriter),
            )
            .upload_string("Hello world!")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_getFileContentFromWorker2_16(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            res = yield x.getFileContentFromWorker("file.txt")
            self.assertEqual(res, "Hello world!")

        self.setup_build(worker_version={'*': '2.16'})
        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(
            ExpectUploadFile(
                slavesrc="file.txt",
                workdir='wkdir',
                blocksize=32 * 1024,
                maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.StringFileWriter),
            )
            .upload_string("Hello world!")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_downloadFileContentToWorker(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            res = yield x.downloadFileContentToWorker("/path/dest1", "file text")
            self.assertEqual(res, None)

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(
            ExpectDownloadFile(
                maxsize=None,
                workdir='wkdir',
                mode=None,
                reader=ExpectRemoteRef(remotetransfer.FileReader),
                blocksize=32768,
                workerdest='/path/dest1',
            )
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_downloadFileContentToWorkerWithFilePermissions(self) -> defer.Deferred[None]:
        @defer.inlineCallbacks
        def testFunc(x: Any) -> InlineCallbacksType[None]:
            res = yield x.downloadFileContentToWorker("/path/dest1", "file text", mode=stat.S_IRUSR)
            self.assertEqual(res, None)

        self.setup_step(CompositeUser(testFunc))
        self.expect_commands(
            ExpectDownloadFile(
                maxsize=None,
                workdir='wkdir',
                mode=stat.S_IRUSR,
                reader=ExpectRemoteRef(remotetransfer.FileReader),
                blocksize=32768,
                workerdest='/path/dest1',
            )
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()
