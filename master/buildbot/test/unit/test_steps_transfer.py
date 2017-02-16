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
from future.utils import iteritems

import json
import os
import shutil
import stat
import tarfile
import tempfile
from io import BytesIO

from mock import Mock

from twisted.trial import unittest

from buildbot import config
from buildbot.process import remotetransfer
from buildbot.process.properties import Properties
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.steps import transfer
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.util import steps
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.util import bytes2NativeString
from buildbot.util import unicode2bytes
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning


def uploadString(string, timestamp=None):
    def behavior(command):
        writer = command.args['writer']
        writer.remote_write(string + "\n")
        writer.remote_close()
        if timestamp:
            writer.remote_utime(timestamp)
    return behavior


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


def uploadTarFile(filename, **members):
    def behavior(command):
        f = BytesIO()
        archive = tarfile.TarFile(fileobj=f, name=filename, mode='w')
        for name, content in iteritems(members):
            content = unicode2bytes(content)
            archive.addfile(tarfile.TarInfo(name), BytesIO(content))
        writer = command.args['writer']
        writer.remote_write(f.getvalue())
        writer.remote_unpack()
    return behavior


class UploadError(object):

    def __init__(self, behavior):
        self.behavior = behavior
        self.writer = None

    def __call__(self, command):
        self.writer = command.args['writer']
        self.writer.cancel = Mock(wraps=self.writer.cancel)
        self.behavior(command)
        raise RuntimeError('uh oh')


class TestFileUpload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)
        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        return self.tearDownBuildStep()

    def testConstructorModeType(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          transfer.FileUpload(workersrc=__file__, masterdest='xyz', mode='g+rwx'))

    def testBasic(self):
        self.setupStep(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="uploading srcfile")
        d = self.runStep()
        return d

    def testWorker2_16(self):
        self.setupStep(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile),
            worker_version={'*': '2.16'})

        self.expectCommands(
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="uploading srcfile")
        d = self.runStep()
        return d

    def testTimestamp(self):
        self.setupStep(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile, keepstamp=True))

        timestamp = (os.path.getatime(__file__),
                     os.path.getmtime(__file__))

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc=__file__, workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=True,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString('test', timestamp=timestamp))
            + 0)

        self.expectOutcome(
            result=SUCCESS,
            state_string="uploading %s" % os.path.basename(__file__))

        d = self.runStep()

        @d.addCallback
        def checkTimestamp(_):
            desttimestamp = (os.path.getatime(self.destfile),
                             os.path.getmtime(self.destfile))

            srctimestamp = [int(t) for t in timestamp]
            desttimestamp = [int(d) for d in desttimestamp]

            self.assertEqual(srctimestamp[0], desttimestamp[0])
            self.assertEqual(srctimestamp[1], desttimestamp[1])
        return d

    def testDescriptionDone(self):
        self.setupStep(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile, url="http://server/file",
                descriptionDone="Test File Uploaded"))

        self.step.addURL = Mock()

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc=__file__, workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS,
            state_string="Test File Uploaded")

        d = self.runStep()
        return d

    def testURL(self):
        self.setupStep(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile, url="http://server/file"))

        self.step.addURL = Mock()

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc=__file__, workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS,
            state_string="uploading %s" % os.path.basename(__file__))

        d = self.runStep()

        @d.addCallback
        def checkURL(_):
            self.step.addURL.assert_called_once_with(
                os.path.basename(self.destfile), "http://server/file")
        return d

    def testURLText(self):
        self.setupStep(
            transfer.FileUpload(workersrc=__file__, masterdest=self.destfile, url="http://server/file", urlText="testfile"))

        self.step.addURL = Mock()

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc=__file__, workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS,
            state_string="uploading %s" % os.path.basename(__file__))

        d = self.runStep()

        @d.addCallback
        def checkURL(_):
            self.step.addURL.assert_called_once_with(
                "testfile", "http://server/file")
        return d

    def testFailure(self):
        self.setupStep(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + 1)

        self.expectOutcome(
            result=FAILURE,
            state_string="uploading srcfile (failure)")
        d = self.runStep()
        return d

    def testException(self):
        self.setupStep(
            transfer.FileUpload(workersrc='srcfile', masterdest=self.destfile))

        behavior = UploadError(uploadString("Hello world!"))

        self.expectCommands(
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(behavior))

        self.expectOutcome(
            result=EXCEPTION, state_string="uploading srcfile (exception)")
        d = self.runStep()

        @d.addCallback
        def check(_):
            self.assertEqual(behavior.writer.cancel.called, True)
            self.assertEqual(
                len(self.flushLoggedErrors(RuntimeError)), 1)

        return d

    def test_workersrc_old_api(self):
        step = transfer.FileUpload(workersrc='srcfile', masterdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workersrc

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavesrc' attribute is deprecated"):
            old = step.slavesrc

        self.assertIdentical(new, old)

    def test_init_workersrc_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.FileUpload(
                workersrc='srcfile', masterdest='dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_workersrc_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavesrc' keyword argument is deprecated"):
            step = transfer.FileUpload(
                slavesrc='srcfile', masterdest='dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_workersrc_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.FileUpload('srcfile', 'dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.FileUpload())
        self.assertRaises(TypeError, lambda: transfer.FileUpload('src'))


class TestDirectoryUpload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        self.destdir = os.path.abspath('destdir')
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.tearDownBuildStep()

    def testBasic(self):
        self.setupStep(
            transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir))

        self.expectCommands(
            Expect('uploadDirectory', dict(
                workersrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading srcdir")
        d = self.runStep()
        return d

    def testWorker2_16(self):
        self.setupStep(
            transfer.DirectoryUpload(
                workersrc="srcdir", masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            Expect('uploadDirectory', dict(
                slavesrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(result=SUCCESS,
                           state_string="uploading srcdir")
        d = self.runStep()
        return d

    def testFailure(self):
        self.setupStep(
            transfer.DirectoryUpload(workersrc="srcdir", masterdest=self.destdir))

        self.expectCommands(
            Expect('uploadDirectory', dict(
                workersrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + 1)

        self.expectOutcome(result=FAILURE,
                           state_string="uploading srcdir (failure)")
        d = self.runStep()
        return d

    def testException(self):
        self.setupStep(
            transfer.DirectoryUpload(workersrc='srcdir', masterdest=self.destdir))

        behavior = UploadError(uploadTarFile('fake.tar', test="Hello world!"))

        self.expectCommands(
            Expect('uploadDirectory', dict(
                workersrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(behavior))

        self.expectOutcome(
            result=EXCEPTION,
            state_string="uploading srcdir (exception)")
        d = self.runStep()

        @d.addCallback
        def check(_):
            self.assertEqual(behavior.writer.cancel.called, True)
            self.assertEqual(
                len(self.flushLoggedErrors(RuntimeError)), 1)

        return d

    def test_workersrc_old_api(self):
        step = transfer.DirectoryUpload(
            workersrc='srcfile', masterdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workersrc

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavesrc' attribute is deprecated"):
            old = step.slavesrc

        self.assertIdentical(new, old)

    def test_init_workersrc_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.DirectoryUpload(
                workersrc='srcfile', masterdest='dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_workersrc_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavesrc' keyword argument is deprecated"):
            step = transfer.DirectoryUpload(
                slavesrc='srcfile', masterdest='dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_workersrc_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.DirectoryUpload('srcfile', 'dstfile')

        self.assertEqual(step.workersrc, 'srcfile')

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.DirectoryUpload())
        self.assertRaises(TypeError, lambda: transfer.DirectoryUpload('src'))


class TestMultipleFileUpload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        self.destdir = os.path.abspath('destdir')
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destdir):
            shutil.rmtree(self.destdir)

        return self.tearDownBuildStep()

    def testEmpty(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs=[], masterdest=self.destdir))

        self.expectCommands()

        self.expectOutcome(result=SKIPPED, state_string="finished (skipped)")
        d = self.runStep()
        return d

    def testFile(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs=["srcfile"], masterdest=self.destdir))

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testDirectory(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs=["srcdir"], masterdest=self.destdir))

        self.expectCommands(
            Expect('stat', dict(file="srcdir",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFDIR, 99, 99])
            + 0,
            Expect('uploadDirectory', dict(
                workersrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testMultiple(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0,
            Expect('stat', dict(file="srcdir",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFDIR, 99, 99])
            + 0,
            Expect('uploadDirectory', dict(
                workersrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="uploading 2 files")
        d = self.runStep()
        return d

    def testMultipleString(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs="srcfile", masterdest=self.destdir))
        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)
        self.expectOutcome(
            result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testGlob(self):
        self.setupStep(
            transfer.MultipleFileUpload(
                workersrcs=["src*"], masterdest=self.destdir, glob=True))
        self.expectCommands(
            Expect('glob', dict(path=os.path.join('wkdir', 'src*'), logEnviron=False))
            + Expect.update('files', ["srcfile"])
            + 0,
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0,
        )
        self.expectOutcome(
            result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testFailedGlob(self):
        self.setupStep(
            transfer.MultipleFileUpload(
                workersrcs=["src*"], masterdest=self.destdir, glob=True))
        self.expectCommands(
            Expect('glob', {'path': os.path.join('wkdir', 'src*'), 'logEnviron': False})
            + Expect.update('files', [])
            + 1,
        )
        self.expectOutcome(result=SKIPPED, state_string="uploading 0 files (skipped)")
        d = self.runStep()
        return d

    def testFileWorker2_16(self):
        self.setupStep(
            transfer.MultipleFileUpload(
                workersrcs=["srcfile"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0)

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testDirectoryWorker2_16(self):
        self.setupStep(
            transfer.MultipleFileUpload(
                workersrcs=["srcdir"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            Expect('stat', dict(file="srcdir",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFDIR, 99, 99])
            + 0,
            Expect('uploadDirectory', dict(
                slavesrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(result=SUCCESS, state_string="uploading 1 file")
        d = self.runStep()
        return d

    def testMultipleWorker2_16(self):
        self.setupStep(
            transfer.MultipleFileUpload(
                workersrcs=["srcfile", "srcdir"], masterdest=self.destdir),
            worker_version={'*': '2.16'})

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0,
            Expect('stat', dict(file="srcdir",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFDIR, 99, 99])
            + 0,
            Expect('uploadDirectory', dict(
                slavesrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="uploading 2 files")
        d = self.runStep()
        return d

    def testFailure(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + 1)

        self.expectOutcome(
            result=FAILURE, state_string="uploading 2 files (failure)")
        d = self.runStep()
        return d

    def testException(self):
        self.setupStep(
            transfer.MultipleFileUpload(workersrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        behavior = UploadError(uploadString("Hello world!"))

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(behavior))

        self.expectOutcome(
            result=EXCEPTION, state_string="uploading 2 files (exception)")
        d = self.runStep()

        @d.addCallback
        def check(_):
            self.assertEqual(behavior.writer.cancel.called, True)
            self.assertEqual(
                len(self.flushLoggedErrors(RuntimeError)), 1)

        return d

    def testSubclass(self):
        class CustomStep(transfer.MultipleFileUpload):
            uploadDone = Mock(return_value=None)
            allUploadsDone = Mock(return_value=None)

        step = CustomStep(
            workersrcs=["srcfile", "srcdir"], masterdest=self.destdir)
        self.setupStep(step)

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                workersrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + Expect.behavior(uploadString("Hello world!"))
            + 0,
            Expect('stat', dict(file="srcdir",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFDIR, 99, 99])
            + 0,
            Expect('uploadDirectory', dict(
                workersrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + Expect.behavior(uploadTarFile('fake.tar', test="Hello world!"))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="uploading 2 files")

        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            self.assertEqual(step.uploadDone.call_count, 2)
            self.assertEqual(step.uploadDone.call_args_list[0],
                             ((SUCCESS, 'srcfile', os.path.join(self.destdir, 'srcfile')), {}))
            self.assertEqual(step.uploadDone.call_args_list[1],
                             ((SUCCESS, 'srcdir', os.path.join(self.destdir, 'srcdir')), {}))
            self.assertEqual(step.allUploadsDone.call_count, 1)
            self.assertEqual(step.allUploadsDone.call_args_list[0],
                             ((SUCCESS, ['srcfile', 'srcdir'], self.destdir), {}))
            return res

        return d

    def test_workersrcs_old_api(self):
        step = transfer.MultipleFileUpload(
            workersrcs=['srcfile'], masterdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workersrcs

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavesrcs' attribute is deprecated"):
            old = step.slavesrcs

        self.assertIdentical(new, old)

    def test_init_workersrcs_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.MultipleFileUpload(
                workersrcs=['srcfile'], masterdest='dstfile')

        self.assertEqual(step.workersrcs, ['srcfile'])

    def test_init_workersrcs_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavesrcs' keyword argument is deprecated"):
            step = transfer.MultipleFileUpload(
                slavesrcs=['srcfile'], masterdest='dstfile')

        self.assertEqual(step.workersrcs, ['srcfile'])

    def test_init_workersrcs_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.MultipleFileUpload(['srcfile'], 'dstfile')

        self.assertEqual(step.workersrcs, ['srcfile'])

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.MultipleFileUpload())
        self.assertRaises(
            TypeError, lambda: transfer.MultipleFileUpload(['srcfile']))


class TestFileDownload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)
        return self.setUpBuildStep()

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)
        return self.tearDownBuildStep()

    def test_workerdest_old_api(self):
        step = transfer.FileDownload(mastersrc='srcfile', workerdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workerdest

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' attribute is deprecated"):
            old = step.slavedest

        self.assertIdentical(new, old)

    def test_init_workerdest_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.FileDownload(
                mastersrc='srcfile', workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' keyword argument is deprecated"):
            step = transfer.FileDownload(
                mastersrc='srcfile', slavedest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.FileDownload('srcfile', 'dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.FileDownload())
        self.assertRaises(TypeError, lambda: transfer.FileDownload('srcfile'))

    def testBasic(self):
        master_file = __file__
        self.setupStep(
            transfer.FileDownload(
                mastersrc=master_file, workerdest=self.destfile))

        # A place to store what gets read
        read = []

        self.expectCommands(
            Expect('downloadFile', dict(
                workerdest=self.destfile, workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.FileReader)))
            + Expect.behavior(downloadString(read.append))
            + 0)

        self.expectOutcome(
            result=SUCCESS,
            state_string="downloading to {0}".format(
                os.path.basename(self.destfile)))
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            with open(master_file, "rb") as f:
                contents = f.read()
            # Only first 1000 bytes transferred in downloadString() helper
            contents = contents[:1000]
            self.assertEqual(b''.join(read), contents)

        return d

    def testBasicWorker2_16(self):
        master_file = __file__
        self.setupStep(
            transfer.FileDownload(
                mastersrc=master_file, workerdest=self.destfile),
            worker_version={'*': '2.16'})

        # A place to store what gets read
        read = []

        self.expectCommands(
            Expect('downloadFile', dict(
                slavedest=self.destfile, workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.FileReader)))
            + Expect.behavior(downloadString(read.append))
            + 0)

        self.expectOutcome(
            result=SUCCESS,
            state_string="downloading to {0}".format(
                os.path.basename(self.destfile)))
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            with open(master_file, "rb") as f:
                contents = f.read()
            # Only first 1000 bytes transferred in downloadString() helper
            contents = contents[:1000]
            self.assertEqual(b''.join(read), contents)

        return d


class TestStringDownload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    # check that ConfigErrors is raised on invalid 'mode' argument

    def testModeConfError(self):
        self.assertRaisesRegex(
            config.ConfigErrors,
            "StringDownload step's mode must be an integer or None,"
            " got 'not-a-number'",
            transfer.StringDownload,
            "string", "file", mode="not-a-number")

    def testBasic(self):
        self.setupStep(transfer.StringDownload("Hello World", "hello.txt"))

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expectCommands(
            Expect('downloadFile', dict(
                workerdest="hello.txt", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader)))
            + Expect.behavior(downloadString(read.append))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to hello.txt")
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            self.assertEqual(b''.join(read), b"Hello World")
        return d

    def testBasicWorker2_16(self):
        self.setupStep(
            transfer.StringDownload("Hello World", "hello.txt"),
            worker_version={'*': '2.16'})

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expectCommands(
            Expect('downloadFile', dict(
                slavedest="hello.txt", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader)))
            + Expect.behavior(downloadString(read.append))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to hello.txt")
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            self.assertEqual(b''.join(read), b"Hello World")
        return d

    def testFailure(self):
        self.setupStep(transfer.StringDownload("Hello World", "hello.txt"))

        self.expectCommands(
            Expect('downloadFile', dict(
                workerdest="hello.txt", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader)))
            + 1)

        self.expectOutcome(
            result=FAILURE, state_string="downloading to hello.txt (failure)")
        return self.runStep()

    def test_workerdest_old_api(self):
        step = transfer.StringDownload('srcfile', workerdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workerdest

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' attribute is deprecated"):
            old = step.slavedest

        self.assertIdentical(new, old)

    def test_init_workerdest_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.StringDownload('srcfile', workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' keyword argument is deprecated"):
            step = transfer.StringDownload('srcfile', slavedest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.StringDownload('srcfile', 'dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.StringDownload())
        self.assertRaises(
            TypeError, lambda: transfer.StringDownload('srcfile'))


class TestJSONStringDownload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        msg = dict(message="Hello World")
        self.setupStep(transfer.JSONStringDownload(msg, "hello.json"))

        self.step.worker = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expectCommands(
            Expect('downloadFile', dict(
                workerdest="hello.json", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            )
            + Expect.behavior(downloadString(read.append))
            + 0)

        self.expectOutcome(
            result=SUCCESS, state_string="downloading to hello.json")
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            self.assertEqual(b''.join(read), b'{"message": "Hello World"}')
        return d

    def testFailure(self):
        msg = dict(message="Hello World")
        self.setupStep(transfer.JSONStringDownload(msg, "hello.json"))

        self.expectCommands(
            Expect('downloadFile', dict(
                workerdest="hello.json", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader)))
            + 1)

        self.expectOutcome(
            result=FAILURE, state_string="downloading to hello.json (failure)")
        return self.runStep()

    def test_workerdest_old_api(self):
        step = transfer.JSONStringDownload('srcfile', workerdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workerdest

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' attribute is deprecated"):
            old = step.slavedest

        self.assertIdentical(new, old)

    def test_init_workerdest_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.JSONStringDownload('srcfile', workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' keyword argument is deprecated"):
            step = transfer.JSONStringDownload('srcfile', slavedest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.JSONStringDownload('srcfile', 'dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.JSONStringDownload())
        self.assertRaises(
            TypeError, lambda: transfer.JSONStringDownload('srcfile'))


class TestJSONPropertiesDownload(unittest.TestCase):

    def testBasic(self):
        s = transfer.JSONPropertiesDownload("props.json")
        s.build = Mock()
        props = Properties()
        props.setProperty('key1', 'value1', 'test')
        s.build.getProperties.return_value = props
        s.build.getWorkerCommandVersion.return_value = '3.0'
        ss = Mock()
        ss.asDict.return_value = dict(revision="12345")
        s.build.getAllSourceStamps.return_value = [ss]

        s.worker = Mock()
        s.remote = Mock()

        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'downloadFile':
                self.assertEqual(kwargs['workerdest'], 'props.json')
                reader = kwargs['reader']
                data = reader.remote_read(100)
                data = bytes2NativeString(data)
                actualJson = json.loads(data)
                expectedJson = dict(sourcestamps=[ss.asDict()], properties={'key1': 'value1'})
                self.assertEqual(actualJson, expectedJson)
                break
        else:
            raise ValueError("No downloadFile command found")

    def testBasicWorker2_16(self):
        s = transfer.JSONPropertiesDownload("props.json")
        s.build = Mock()
        props = Properties()
        props.setProperty('key1', 'value1', 'test')
        s.build.getProperties.return_value = props
        s.build.getWorkerCommandVersion.return_value = '2.16'
        ss = Mock()
        ss.asDict.return_value = dict(revision="12345")
        s.build.getAllSourceStamps.return_value = [ss]

        s.worker = Mock()
        s.remote = Mock()

        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'downloadFile':
                self.assertEqual(kwargs['slavedest'], 'props.json')
                reader = kwargs['reader']
                data = reader.remote_read(100)
                data = bytes2NativeString(data)
                actualJson = json.loads(data)
                expectedJson = dict(sourcestamps=[ss.asDict()], properties={'key1': 'value1'})
                self.assertEqual(actualJson, expectedJson)
                break
        else:
            raise ValueError("No downloadFile command found")

    def test_workerdest_old_api(self):
        step = transfer.JSONPropertiesDownload(workerdest='dstfile')

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = step.workerdest

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' attribute is deprecated"):
            old = step.slavedest

        self.assertIdentical(new, old)

    def test_init_workerdest_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.JSONPropertiesDownload(workerdest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavedest' keyword argument is deprecated"):
            step = transfer.JSONPropertiesDownload(slavedest='dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_workerdest_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            step = transfer.JSONPropertiesDownload('dstfile')

        self.assertEqual(step.workerdest, 'dstfile')

    def test_init_positional_args(self):
        self.assertRaises(TypeError, lambda: transfer.JSONPropertiesDownload())
