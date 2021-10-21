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
import stat
import tempfile

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process import remotetransfer
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.steps import transfer
from buildbot.test.fake.remotecommand import ExpectDownloadFile
from buildbot.test.fake.remotecommand import ExpectGlob
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectStat
from buildbot.test.fake.remotecommand import ExpectUploadDirectory
from buildbot.test.fake.remotecommand import ExpectUploadFile
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin


def downloadString(memoizer, timestamp=None):
    def behavior(command):
        reader = command.args['reader']
        read = reader.remote_read(1000)
        # save what we read so we can check it
        memoizer(read)
        reader.remote_close()
        if timestamp:
            reader.remote_utime(timestamp)
        return read
    return behavior


class TestFileUpload(steps.BuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)
        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        return self.tearDownBuildStep()

    def testConstructorModeType(self):
        with self.assertRaises(config.ConfigErrors):
            transfer.FileUpload(workersrc=__file__,
                                masterdest='xyz', mode='g+rwx')

    def testBasic(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expectCommands(
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="uploading srcfile")
        d = self.runStep()
        return d

    def testWorker2_16(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile),
            worker_version={'*': '2.16'})

        self.expectCommands(
            ExpectUploadFile(slavesrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="uploading srcfile")
        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def testTimestamp(self):
        self.setup_step(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile, keepstamp=True))

        timestamp = (os.path.getatime(__file__),
                     os.path.getmtime(__file__))

        self.expectCommands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=True,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string('test\n', timestamp=timestamp)
            .exit(0))

        self.expectOutcome(
            result=SUCCESS,
            state_string="uploading {}".format(os.path.basename(__file__))
            )

        yield self.runStep()

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

        self.expectCommands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(
            result=SUCCESS,
            state_string="Test File Uploaded")

        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def testURL(self):
        self.setup_step(transfer.FileUpload(workersrc=__file__, masterdest=self.destfile,
                                           url="http://server/file"))

        self.step.addURL = Mock()

        self.expectCommands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(
            result=SUCCESS,
            state_string="uploading {}".format(os.path.basename(__file__))
            )

        yield self.runStep()

        self.step.addURL.assert_called_once_with(
            os.path.basename(self.destfile), "http://server/file")

    @defer.inlineCallbacks
    def testURLText(self):
        self.setup_step(transfer.FileUpload(workersrc=__file__,
                                           masterdest=self.destfile, url="http://server/file",
                                           urlText="testfile"))

        self.step.addURL = Mock()

        self.expectCommands(
            ExpectUploadFile(workersrc=__file__, workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(
            result=SUCCESS,
            state_string="uploading {}".format(os.path.basename(__file__))
            )

        yield self.runStep()

        self.step.addURL.assert_called_once_with(
            "testfile", "http://server/file")

    def testFailure(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expectCommands(
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .exit(1))

        self.expectOutcome(
            result=FAILURE,
            state_string="uploading srcfile (failure)")
        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def testException(self):
        self.setup_step(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        writers = []

        self.expectCommands(
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=262144, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n", out_writers=writers, error=RuntimeError('uh oh')))

        self.expectOutcome(
            result=EXCEPTION, state_string="uploading srcfile (exception)")
        yield self.runStep()

        self.assertEqual(len(writers), 1)
        self.assertEqual(writers[0].cancel.called, True)

        self.assertEqual(
            len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_interrupt(self):
        self.setup_step(transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expectCommands(
            ExpectUploadFile(workersrc='srcfile', workdir='wkdir', blocksize=262144,
                             maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter),
                             interrupted=True)
            .exit(0))

        self.interrupt_nth_remote_command(0)

        self.expectOutcome(result=CANCELLED,
                           state_string="uploading srcfile (cancelled)")
        self.expectLogfile('interrupt', 'interrupt reason')
        yield self.runStep()

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


class TestDirectoryUpload(steps.BuildStepMixin, TestReactorMixin,
                          unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.destdir = os.path.abspath('destdir')
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.tearDownBuildStep()

    def testBasic(self):
        self.setup_step(
            transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir))

        self.expectCommands(
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading srcdir")
        d = self.runStep()
        return d

    def testWorker2_16(self):
        self.setup_step(
            transfer.DirectoryUpload(
                workersrc="srcdir", masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            ExpectUploadDirectory(slavesrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading srcdir")
        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def test_url(self):
        self.setup_step(transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir,
                                                url="http://server/dir"))

        self.step.addURL = Mock()

        self.expectCommands(
            ExpectUploadDirectory(workersrc='srcdir', workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading srcdir")

        yield self.runStep()

        self.step.addURL.assert_called_once_with("destdir", "http://server/dir")

    @defer.inlineCallbacks
    def test_url_text(self):
        self.setup_step(transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir,
                                                url="http://server/dir", urlText='url text'))

        self.step.addURL = Mock()

        self.expectCommands(
            ExpectUploadDirectory(workersrc='srcdir', workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading srcdir")

        yield self.runStep()

        self.step.addURL.assert_called_once_with("url text", "http://server/dir")

    @defer.inlineCallbacks
    def testFailure(self):
        self.setup_step(
            transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir))

        self.expectCommands(
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .exit(1))

        self.expectOutcome(result=FAILURE,
                           state_string="uploading srcdir (failure)")
        yield self.runStep()

    @defer.inlineCallbacks
    def testException(self):
        self.setup_step(
            transfer.DirectoryUpload(workersrc='srcdir', masterdest=self.destdir))

        writers = []

        self.expectCommands(
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"}, error=RuntimeError('uh oh'),
                             out_writers=writers))

        self.expectOutcome(
            result=EXCEPTION,
            state_string="uploading srcdir (exception)")
        yield self.runStep()

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


class TestMultipleFileUpload(steps.BuildStepMixin, TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.destdir = os.path.abspath('destdir')
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.tearDownBuildStep()

    def testEmpty(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=[], masterdest=self.destdir))

        self.expectCommands()

        self.expectOutcome(result=SKIPPED, state_string="finished (skipped)")
        d = self.runStep()
        return d

    def testFile(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir))

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testDirectory(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expectCommands(
            ExpectStat(file="srcdir", workdir='wkdir')
            .update('stat', [stat.S_IFDIR, 99, 99])
            .exit(0),
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def test_not_existing_path(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expectCommands(
            ExpectStat(file='srcdir', workdir='wkdir')
            .exit(1))

        self.expectOutcome(result=FAILURE, state_string="uploading 1 file (failure)")
        self.expectLogfile('stderr',
                           "File wkdir/srcdir not available at worker")

        yield self.runStep()

    @defer.inlineCallbacks
    def test_special_path(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expectCommands(
            ExpectStat(file='srcdir', workdir='wkdir')
            .update('stat', [0, 99, 99])
            .exit(0))

        self.expectOutcome(result=FAILURE, state_string="uploading 1 file (failure)")
        self.expectLogfile('stderr', 'srcdir is neither a regular file, nor a directory')

        yield self.runStep()

    def testMultiple(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0),
            ExpectStat(file="srcdir", workdir='wkdir')
            .update('stat', [stat.S_IFDIR, 99, 99])
            .exit(0),
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="uploading 2 files")
        d = self.runStep()
        return d

    def testMultipleString(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs="srcfile", masterdest=self.destdir))
        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))
        self.expectOutcome(
            result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testGlob(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["src*"], masterdest=self.destdir, glob=True))
        self.expectCommands(
            ExpectGlob(path=os.path.join('wkdir', 'src*'), logEnviron=False)
            .update('files', ["srcfile"])
            .exit(0),
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0)
        )
        self.expectOutcome(
            result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testFailedGlob(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["src*"], masterdest=self.destdir, glob=True))
        self.expectCommands(
            ExpectGlob(path=os.path.join('wkdir', 'src*'), logEnviron=False)
            .update('files', [])
            .exit(1)
        )
        self.expectOutcome(
            result=SKIPPED, state_string="uploading 0 files (skipped)")
        d = self.runStep()
        return d

    def testFileWorker2_16(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["srcfile"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(slavesrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testDirectoryWorker2_16(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["srcdir"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            ExpectStat(file="srcdir", workdir='wkdir')
            .update('stat', [stat.S_IFDIR, 99, 99])
            .exit(0),
            ExpectUploadDirectory(slavesrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testMultipleWorker2_16(self):
        self.setup_step(
            transfer.MultipleFileUpload(
                workersrcs=["srcfile", "srcdir"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(slavesrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0),
            ExpectStat(file="srcdir", workdir='wkdir')
            .update('stat', [stat.S_IFDIR, 99, 99])
            .exit(0),
            ExpectUploadDirectory(slavesrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="uploading 2 files")
        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def test_url(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir,
                                                   url="http://server/dir"))

        self.step.addURL = Mock()

        self.expectCommands(
            ExpectStat(file='srcfile', workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc='srcfile', workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading 1 file")

        yield self.runStep()

        self.step.addURL.assert_called_once_with("destdir", "http://server/dir")

    @defer.inlineCallbacks
    def test_url_text(self):
        self.setup_step(transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir,
                                                   url="http://server/dir", urlText='url text'))

        self.step.addURL = Mock()

        self.expectCommands(
            ExpectStat(file='srcfile', workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc='srcfile', workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0))

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading 1 file")

        yield self.runStep()

        self.step.addURL.assert_called_once_with("url text", "http://server/dir")

    def testFailure(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .exit(1))

        self.expectOutcome(
            result=FAILURE, state_string="uploading 2 files (failure)")
        d = self.runStep()
        return d

    @defer.inlineCallbacks
    def testException(self):
        self.setup_step(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        writers = []

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n", out_writers=writers, error=RuntimeError('uh oh')))

        self.expectOutcome(
            result=EXCEPTION, state_string="uploading 2 files (exception)")
        yield self.runStep()

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

        self.expectCommands(
            ExpectStat(file="srcfile", workdir='wkdir')
            .update('stat', [stat.S_IFREG, 99, 99])
            .exit(0),
            ExpectUploadFile(workersrc="srcfile", workdir='wkdir',
                             blocksize=16384, maxsize=None, keepstamp=False,
                             writer=ExpectRemoteRef(remotetransfer.FileWriter))
            .upload_string("Hello world!\n")
            .exit(0),
            ExpectStat(file="srcdir", workdir='wkdir')
            .update('stat', [stat.S_IFDIR, 99, 99])
            .exit(0),
            ExpectUploadDirectory(workersrc="srcdir", workdir='wkdir',
                                  blocksize=16384, compress=None, maxsize=None,
                                  writer=ExpectRemoteRef(remotetransfer.DirectoryWriter))
            .upload_tar_file('fake.tar', {"test": "Hello world!"})
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="uploading 2 files")

        yield self.runStep()

        def checkCalls(res):
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


class TestFileDownload(steps.BuildStepMixin, TestReactorMixin,
                       unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)
        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        return self.tearDownBuildStep()

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

        self.expectCommands(
            ExpectDownloadFile(workerdest=self.destfile, workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader))
            .behavior(downloadString(read.append))
            .exit(0))

        self.expectOutcome(
            result=SUCCESS,
            state_string="downloading to {0}".format(
                os.path.basename(self.destfile)))
        yield self.runStep()

        with open(master_file, "rb") as f:
            contents = f.read()
        # Only first 1000 bytes transferred in downloadString() helper
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

        self.expectCommands(
            ExpectDownloadFile(slavedest=self.destfile, workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader))
            .behavior(downloadString(read.append))
            .exit(0))

        self.expectOutcome(
            result=SUCCESS,
            state_string="downloading to {0}".format(
                os.path.basename(self.destfile)))
        yield self.runStep()

        def checkCalls(res):
            with open(master_file, "rb") as f:
                contents = f.read()
            # Only first 1000 bytes transferred in downloadString() helper
            contents = contents[:1000]
            self.assertEqual(b''.join(read), contents)

    @defer.inlineCallbacks
    def test_no_file(self):
        self.setup_step(transfer.FileDownload(mastersrc='not existing file',
                                             workerdest=self.destfile))

        self.expectCommands()

        self.expectOutcome(result=FAILURE,
                           state_string="downloading to {0} (failure)".format(
                               os.path.basename(self.destfile)))
        self.expectLogfile('stderr',
                           "File 'not existing file' not available at master")
        yield self.runStep()


class TestStringDownload(steps.BuildStepMixin, TestReactorMixin,
                         unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

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

        self.expectCommands(
            ExpectDownloadFile(workerdest="hello.txt", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .behavior(downloadString(read.append))
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to hello.txt")
        yield self.runStep()

        def checkCalls(res):
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

        self.expectCommands(
            ExpectDownloadFile(slavedest="hello.txt", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .behavior(downloadString(read.append))
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to hello.txt")
        yield self.runStep()

        self.assertEqual(b''.join(read), b"Hello World")

    def testFailure(self):
        self.setup_step(transfer.StringDownload("Hello World", "hello.txt"))

        self.expectCommands(
            ExpectDownloadFile(workerdest="hello.txt", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .exit(1))

        self.expectOutcome(
            result=FAILURE, state_string="downloading to hello.txt (failure)")
        return self.runStep()

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


class TestJSONStringDownload(steps.BuildStepMixin, TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    @defer.inlineCallbacks
    def testBasic(self):
        msg = dict(message="Hello World")
        self.setup_step(transfer.JSONStringDownload(msg, "hello.json"))

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expectCommands(
            ExpectDownloadFile(workerdest="hello.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .behavior(downloadString(read.append))
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to hello.json")
        yield self.runStep()

        self.assertEqual(b''.join(read), b'{"message": "Hello World"}')

    def testFailure(self):
        msg = dict(message="Hello World")
        self.setup_step(transfer.JSONStringDownload(msg, "hello.json"))

        self.expectCommands(
            ExpectDownloadFile(workerdest="hello.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .exit(1))

        self.expectOutcome(
            result=FAILURE, state_string="downloading to hello.json (failure)")
        return self.runStep()

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


class TestJSONPropertiesDownload(steps.BuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    @defer.inlineCallbacks
    def testBasic(self):
        self.setup_step(transfer.JSONPropertiesDownload("props.json"))
        self.step.build.setProperty('key1', 'value1', 'test')
        read = []
        self.expectCommands(
            ExpectDownloadFile(workerdest="props.json", workdir='wkdir',
                               blocksize=16384, maxsize=None, mode=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            .behavior(downloadString(read.append))
            .exit(0))

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to props.json")
        yield self.runStep()
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
