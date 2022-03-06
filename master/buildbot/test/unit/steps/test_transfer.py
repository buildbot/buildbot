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

import json
import os
import shutil
import tempfile

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process import remotetransfer
from buildbot.process.properties import Interpolate
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.steps import transfer
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectGlob
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectStat
from buildbot.test.steps import ExpectUploadDirectory
from buildbot.test.steps import ExpectUploadFile
from buildbot.test.steps import TestBuildStepMixin


class TestFileUpload(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)
        return self.setup_test_build_step()

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        return self.tear_down_test_build_step()

    def testConstructorModeType(self):
        with self.assertRaises(config.ConfigErrors):
            transfer.FileUpload(workersrc=__file__,
                                masterdest='xyz', mode='g+rwx')

    def testBasic(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expect_commands(
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="uploading srcfile")
        d = self.run_step()
        return d

    def testWorker2_16(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile),
            worker_version={'*': '2.16'})

        self.expect_commands(
            ExpectUploadFile(slavesrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="uploading srcfile")
        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def testTimestamp(self):
        self.setup_step(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile, keepstamp=True))

        timestamp = (os.path.getatime(__file__),
                     os.path.getmtime(__file__))

        self.expect_commands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=True,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string('test\n', timestamp=timestamp)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS,
            state_string=f"uploading {os.path.basename(__file__)}"
            )

        yield self.run_step()

        desttimestamp = (os.path.getatime(self.destfile),
                         os.path.getmtime(self.destfile))

        srctimestamp = [int(t) for t in timestamp]
        desttimestamp = [int(d) for d in desttimestamp]

        self.assertEqual(srctimestamp[0], desttimestamp[0])
        self.assertEqual(srctimestamp[1], desttimestamp[1])

    def testDescriptionDone(self):
        self.setup_step(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile,
                                url="http://server/file", descriptionDone="Test File Uploaded"))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(
            result=SUCCESS,
            state_string="Test File Uploaded")

        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def testURL(self):
        self.setup_step(transfer.FileUpload(workersrc=__file__, masterdest=self.destfile,
                                           url="http://server/file"))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(
            result=SUCCESS,
            state_string=f"uploading {os.path.basename(__file__)}"
            )

        yield self.run_step()

        self.step.addURL.assert_called_once_with(
            os.path.basename(self.destfile), "http://server/file")

    @defer.inlineCallbacks
    def testURLText(self):
        self.setup_step(transfer.FileUpload(workersrc=__file__,
                                           masterdest=self.destfile, url="http://server/file",
                                           urlText="testfile"))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(
            result=SUCCESS,
            state_string=f"uploading {os.path.basename(__file__)}"
            )

        yield self.run_step()

        self.step.addURL.assert_called_once_with(
            "testfile", "http://server/file")

    def testFailure(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expect_commands(
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .exit(1))

        self.expect_outcome(
            result=FAILURE,
            state_string="uploading srcfile (failure)")
        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def testException(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        writers = []

        self.expect_commands(
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n", out_writers=writers, error=RuntimeError('uh oh')))

        self.expect_outcome(
            result=EXCEPTION, state_string="uploading srcfile (exception)")
        yield self.run_step()

        self.assertEqual(len(writers), 1)
        self.assertEqual(writers[0].cancel.called, True)

        self.assertEqual(
            len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_interrupt(self):
        self.setup_step(transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expect_commands(
            ExpectUploadFile(workersrc='srcfile', workdir='wkdir', blocksize=262144,
                             maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter),
                             interrupted=True)
            .exit(0))

        self.interrupt_nth_remote_command(0)

        self.expect_outcome(result=CANCELLED,
                           state_string="uploading srcfile (cancelled)")
        self.expect_log_file('interrupt', 'interrupt reason')
        yield self.run_step()

    def test_init_workersrc_keyword(self):
        step = transfer.FileUpload(
            workersrc='srcfile', masterdest='dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_workersrc_positional(self):
        step = transfer.FileUpload('srcfile', 'dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.FileUpload()
        with self.assertRaises(TypeError):
            transfer.FileUpload('src')


class TestDirectoryUpload(TestBuildStepMixin, TestReactorMixin,
                          unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.destdir = os.path.abspath('destdir')
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.setup_test_build_step()

    def tearDown(self):
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.tear_down_test_build_step()

    def testBasic(self):
        self.setup_step(
            transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir))

        self.expect_commands(
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(result=SUCCESS,
                           state_string="uploading srcdir")
        d = self.run_step()
        return d

    def testWorker2_16(self):
        self.setup_step(
            transfer.DirectoryUpload(
                workersrc="srcdir", masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expect_commands(
            ExpectUploadDirectory(slavesrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(result=SUCCESS,
                           state_string="uploading srcdir")
        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def test_url(self):
        self.setup_step(transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir,
                                                url="http://server/dir"))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectUploadDirectory(workersrc='srcdir', workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(result=SUCCESS,
                           state_string="uploading srcdir")

        yield self.run_step()

        self.step.addURL.assert_called_once_with("destdir", "http://server/dir")

    @defer.inlineCallbacks
    def test_url_text(self):
        self.setup_step(transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir,
                                                url="http://server/dir", urlText='url text'))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectUploadDirectory(workersrc='srcdir', workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(result=SUCCESS,
                           state_string="uploading srcdir")

        yield self.run_step()

        self.step.addURL.assert_called_once_with("url text", "http://server/dir")

    @defer.inlineCallbacks
    def testFailure(self):
        self.setup_step(
            transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir))

        self.expect_commands(
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .exit(1))

        self.expect_outcome(result=FAILURE,
                           state_string="uploading srcdir (failure)")
        yield self.run_step()

    @defer.inlineCallbacks
    def testException(self):
        self.setup_step(
            transfer.DirectoryUpload(workersrc='srcdir', masterdest=self.destdir))

        writers = []

        self.expect_commands(
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"}, error=RuntimeError('uh oh'),
                             out_writers=writers))

        self.expect_outcome(
            result=EXCEPTION,
            state_string="uploading srcdir (exception)")
        yield self.run_step()

        self.assertEqual(len(writers), 1)
        self.assertEqual(writers[0].cancel.called, True)

        self.assertEqual(
            len(self.flushLoggedErrors(RuntimeError)), 1)

    def test_init_workersrc_keyword(self):
        step = transfer.DirectoryUpload(
            workersrc='srcfile', masterdest='dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_workersrc_positional(self):
        step = transfer.DirectoryUpload('srcfile', 'dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.DirectoryUpload()
        with self.assertRaises(TypeError):
            transfer.DirectoryUpload('src')


class TestMultipleFileUpload(TestBuildStepMixin, TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.destdir = os.path.abspath('destdir')
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.setup_test_build_step()

    def tearDown(self):
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.tear_down_test_build_step()

    def testEmpty(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=[], masterdest=self.destdir))

        self.expect_commands()

        self.expect_outcome(result=SKIPPED, state_string="finished (skipped)")
        d = self.run_step()
        return d

    def testFile(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir))

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.run_step()
        return d

    def testDirectory(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expect_commands(
            ExpectStat(file="srcdir", workdir='wkdir')
            .stat_dir()
            .exit(0),
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def test_not_existing_path(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expect_commands(
            ExpectStat(file='srcdir', workdir='wkdir')
            .exit(1))

        self.expect_outcome(result=FAILURE, state_string="uploading 1 file (failure)")
        self.expect_log_file('stderr',
                           "File wkdir/srcdir not available at worker")

        yield self.run_step()

    @defer.inlineCallbacks
    def test_special_path(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expect_commands(
            ExpectStat(file='srcdir', workdir='wkdir')
            .stat(mode=0)
            .exit(0))

        self.expect_outcome(result=FAILURE, state_string="uploading 1 file (failure)")
        self.expect_log_file('stderr', 'srcdir is neither a regular file, nor a directory')

        yield self.run_step()

    def testMultiple(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0),
            ExpectStat(file="srcdir", workdir='wkdir')
            .stat_dir()
            .exit(0),
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="uploading 2 files")
        d = self.run_step()
        return d

    def testMultipleString(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs="srcfile", masterdest=self.destdir))
        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))
        self.expect_outcome(
            result=SUCCESS, state_string="uploading 1 file")
        d = self.run_step()
        return d

    def testGlob(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["src*"], masterdest=self.destdir, glob=True))
        self.expect_commands(
            ExpectGlob(path=os.path.join('wkdir', 'src*'), log_environ=False)
            .files(["srcfile"])
            .exit(0),
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0)
        )
        self.expect_outcome(
            result=SUCCESS, state_string="uploading 1 file")
        d = self.run_step()
        return d

    def testFailedGlob(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["src*"], masterdest=self.destdir, glob=True))
        self.expect_commands(
            ExpectGlob(path=os.path.join('wkdir', 'src*'), log_environ=False)
            .files()
            .exit(1)
        )
        self.expect_outcome(
            result=SKIPPED, state_string="uploading 0 files (skipped)")
        d = self.run_step()
        return d

    def testFileWorker2_16(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["srcfile"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(slavesrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.run_step()
        return d

    def testDirectoryWorker2_16(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["srcdir"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expect_commands(
            ExpectStat(file="srcdir", workdir='wkdir')
            .stat_dir()
            .exit(0),
            ExpectUploadDirectory(slavesrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.run_step()
        return d

    def testMultipleWorker2_16(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["srcfile", "srcdir"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(slavesrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0),
            ExpectStat(file="srcdir", workdir='wkdir')
            .stat_dir()
            .exit(0),
            ExpectUploadDirectory(slavesrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="uploading 2 files")
        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def test_url(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir,
                                                   url="http://server/dir"))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectStat(file='srcfile', workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc='srcfile', workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(result=SUCCESS,
                           state_string="uploading 1 file")

        yield self.run_step()

        self.step.addURL.assert_called_once_with("destdir", "http://server/dir")

    @defer.inlineCallbacks
    def test_url_text(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir,
                                                   url="http://server/dir", urlText='url text'))

        self.step.addURL = Mock()

        self.expect_commands(
            ExpectStat(file='srcfile', workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc='srcfile', workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expect_outcome(result=SUCCESS,
                           state_string="uploading 1 file")

        yield self.run_step()

        self.step.addURL.assert_called_once_with("url text", "http://server/dir")

    def testFailure(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .exit(1))

        self.expect_outcome(
            result=FAILURE, state_string="uploading 2 files (failure)")
        d = self.run_step()
        return d

    @defer.inlineCallbacks
    def testException(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        writers = []

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n", out_writers=writers, error=RuntimeError('uh oh')))

        self.expect_outcome(
            result=EXCEPTION, state_string="uploading 2 files (exception)")
        yield self.run_step()

        self.assertEqual(len(writers), 1)
        self.assertEqual(writers[0].cancel.called, True)

        self.assertEqual(
            len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def testSubclass(self):
        class CustomStep(transfer.MultipleFileUpload):
            uploadDone = Mock(return_value=None)
            allUploadsDone = Mock(return_value=None)

        step = CustomStep(
            workersrcs=["srcfile", "srcdir"], masterdest=self.destdir)
        self.setup_step(step)

        self.expect_commands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .stat_file()
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0),
            ExpectStat(file="srcdir", workdir='wkdir')
            .stat_dir()
            .exit(0),
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="uploading 2 files")

        yield self.run_step()

        self.assertEqual(step.uploadDone.call_count, 2)
        self.assertEqual(step.uploadDone.call_args_list[0],
                         ((SUCCESS, 'srcfile', os.path.join(self.destdir, 'srcfile')), {}))
        self.assertEqual(step.uploadDone.call_args_list[1],
                         ((SUCCESS, 'srcdir', os.path.join(self.destdir, 'srcdir')), {}))
        self.assertEqual(step.allUploadsDone.call_count, 1)
        self.assertEqual(step.allUploadsDone.call_args_list[0],
                         ((SUCCESS, ['srcfile', 'srcdir'], self.destdir), {}))

    def test_init_workersrcs_keyword(self):
        step = transfer.MultipleFileUpload(
            workersrcs=['srcfile'], masterdest='dstfile')

        self.assertEqual(step.workersrcs, ['srcfile'])

    def test_init_workersrcs_positional(self):
        step = transfer.MultipleFileUpload(['srcfile'], 'dstfile')

        self.assertEqual(step.workersrcs, ['srcfile'])

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.MultipleFileUpload()
        with self.assertRaises(TypeError):
            transfer.MultipleFileUpload(['srcfile'])


class TestFileDownload(TestBuildStepMixin, TestReactorMixin,
                       unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)
        return self.setup_test_build_step()

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        return self.tear_down_test_build_step()

    def test_init_workerdest_keyword(self):
        step = transfer.FileDownload(
            mastersrc='srcfile', workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        step = transfer.FileDownload('srcfile', 'dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.FileDownload()
        with self.assertRaises(TypeError):
            transfer.FileDownload('srcfile')

    @defer.inlineCallbacks
    def testBasic(self):
        master_file = __file__
        self.setup_step(
            transfer.FileDownload(
                mastersrc=master_file, workerdest=self.destfile))

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectDownloadFile(workerdest=self.destfile, workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader))
            .download_string(read.append, size=1000)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS,
            state_string=f"downloading to {os.path.basename(self.destfile)}")
        yield self.run_step()

        with open(master_file, "rb") as f:
            contents = f.read()
        contents = contents[:1000]
        self.assertEqual(b''.join(read), contents)

    @defer.inlineCallbacks
    def testBasicWorker2_16(self):
        master_file = __file__
        self.setup_step(
            transfer.FileDownload(
                mastersrc=master_file, workerdest=self.destfile),
            worker_version={'*': '2.16'})

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectDownloadFile(slavedest=self.destfile, workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader))
            .download_string(read.append, size=1000)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS,
            state_string=f"downloading to {os.path.basename(self.destfile)}")
        yield self.run_step()

        with open(master_file, "rb") as f:
            contents = f.read()
        contents = contents[:1000]
        self.assertEqual(b''.join(read), contents)

    @defer.inlineCallbacks
    def test_no_file(self):
        self.setup_step(transfer.FileDownload(mastersrc='not existing file',
                                             workerdest=self.destfile))

        self.expect_commands()

        self.expect_outcome(result=FAILURE,
                           state_string=f"downloading to {os.path.basename(self.destfile)} "
                           "(failure)")
        self.expect_log_file('stderr',
                           "File 'not existing file' not available at master")
        yield self.run_step()


class TestStringDownload(TestBuildStepMixin, TestReactorMixin,
                         unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    # check that ConfigErrors is raised on invalid 'mode' argument

    def testModeConfError(self):
        with self.assertRaisesRegex(config.ConfigErrors,
                                    "StringDownload step's mode must be an integer or None,"
                                    " got 'not-a-number'"):
            transfer.StringDownload("string", "file", mode="not-a-number")

    @defer.inlineCallbacks
    def testBasic(self):
        self.setup_step(transfer.StringDownload("Hello World", "hello.txt"))

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectDownloadFile(workerdest="hello.txt", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .download_string(read.append)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="downloading to hello.txt")
        yield self.run_step()

        self.assertEqual(b''.join(read), b"Hello World")

    @defer.inlineCallbacks
    def testBasicWorker2_16(self):
        self.setup_step(
            transfer.StringDownload("Hello World", "hello.txt"),
            worker_version={'*': '2.16'})

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectDownloadFile(slavedest="hello.txt", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .download_string(read.append)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="downloading to hello.txt")
        yield self.run_step()

        self.assertEqual(b''.join(read), b"Hello World")

    def testFailure(self):
        self.setup_step(transfer.StringDownload("Hello World", "hello.txt"))

        self.expect_commands(
            ExpectDownloadFile(workerdest="hello.txt", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .exit(1))

        self.expect_outcome(
            result=FAILURE, state_string="downloading to hello.txt (failure)")
        return self.run_step()

    def test_init_workerdest_keyword(self):
        step = transfer.StringDownload('srcfile', workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        step = transfer.StringDownload('srcfile', 'dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.StringDownload()
        with self.assertRaises(TypeError):
            transfer.StringDownload('srcfile')


class TestJSONStringDownload(TestBuildStepMixin, TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    @defer.inlineCallbacks
    def testBasic(self):
        msg = dict(message="Hello World")
        self.setup_step(transfer.JSONStringDownload(msg, "hello.json"))

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectDownloadFile(workerdest="hello.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .download_string(read.append)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="downloading to hello.json")
        yield self.run_step()

        self.assertEqual(b''.join(read), b'{"message": "Hello World"}')

    @defer.inlineCallbacks
    def test_basic_with_renderable(self):
        msg = dict(message=Interpolate("Hello World"))
        self.setup_step(transfer.JSONStringDownload(msg, "hello.json"))

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectDownloadFile(workerdest="hello.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .download_string(read.append)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="downloading to hello.json")
        yield self.run_step()

        self.assertEqual(b''.join(read), b'{"message": "Hello World"}')

    def testFailure(self):
        msg = dict(message="Hello World")
        self.setup_step(transfer.JSONStringDownload(msg, "hello.json"))

        self.expect_commands(
            ExpectDownloadFile(workerdest="hello.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .exit(1))

        self.expect_outcome(
            result=FAILURE, state_string="downloading to hello.json (failure)")
        return self.run_step()

    def test_init_workerdest_keyword(self):
        step = transfer.JSONStringDownload('srcfile', workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        step = transfer.JSONStringDownload('srcfile', 'dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.JSONStringDownload()
        with self.assertRaises(TypeError):
            transfer.JSONStringDownload('srcfile')


class TestJSONPropertiesDownload(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    @defer.inlineCallbacks
    def testBasic(self):
        self.setup_step(transfer.JSONPropertiesDownload("props.json"))
        self.step.build.setProperty('key1', 'value1', 'test')
        read = []
        self.expect_commands(
            ExpectDownloadFile(workerdest="props.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .download_string(read.append)
            .exit(0))

        self.expect_outcome(
            result=SUCCESS, state_string="downloading to props.json")
        yield self.run_step()
        # we decode as key order is dependent of python version
        self.assertEqual(json.loads((b''.join(read)).decode()), {
                         "properties": {"key1": "value1"}, "sourcestamps": []})

    def test_init_workerdest_keyword(self):
        step = transfer.JSONPropertiesDownload(workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        step = transfer.JSONPropertiesDownload('dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        with self.assertRaises(TypeError):
            transfer.JSONPropertiesDownload()
