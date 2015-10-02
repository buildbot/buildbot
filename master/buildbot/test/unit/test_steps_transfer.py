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
from future.utils import iteritems

import os
import shutil
import stat
import tarfile
import tempfile

from twisted.trial import unittest

from mock import Mock

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
from buildbot.util import json

from cStringIO import StringIO


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
        f = StringIO()
        archive = tarfile.TarFile(fileobj=f, name=filename, mode='w')
        for name, content in iteritems(members):
            archive.addfile(tarfile.TarInfo(name), StringIO(content))
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
                          transfer.FileUpload(slavesrc=__file__, masterdest='xyz', mode='g+rwx'))

    def testBasic(self):
        self.setupStep(
            transfer.FileUpload(slavesrc='srcfile', masterdest=self.destfile))

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
            transfer.FileUpload(slavesrc=__file__, masterdest=self.destfile, keepstamp=True))

        timestamp = (os.path.getatime(__file__),
                     os.path.getmtime(__file__))

        self.expectCommands(
            Expect('uploadFile', dict(
                slavesrc=__file__, workdir='wkdir',
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

            srctimestamp = map(int, timestamp)
            desttimestamp = map(int, desttimestamp)

            self.assertEquals(srctimestamp[0], desttimestamp[0])
            self.assertEquals(srctimestamp[1], desttimestamp[1])
        return d

    def testURL(self):
        self.setupStep(
            transfer.FileUpload(slavesrc=__file__, masterdest=self.destfile, url="http://server/file"))

        self.step.addURL = Mock()

        self.expectCommands(
            Expect('uploadFile', dict(
                slavesrc=__file__, workdir='wkdir',
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

    def testFailure(self):
        self.setupStep(
            transfer.FileUpload(slavesrc='srcfile', masterdest=self.destfile))

        self.expectCommands(
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
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
            transfer.FileUpload(slavesrc='srcfile', masterdest=self.destfile))

        behavior = UploadError(uploadString("Hello world!"))

        self.expectCommands(
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
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
            transfer.DirectoryUpload(slavesrc="srcdir", masterdest=self.destdir))

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
            transfer.DirectoryUpload(slavesrc="srcdir", masterdest=self.destdir))

        self.expectCommands(
            Expect('uploadDirectory', dict(
                slavesrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(remotetransfer.DirectoryWriter)))
            + 1)

        self.expectOutcome(result=FAILURE,
                           state_string="uploading srcdir (failure)")
        d = self.runStep()
        return d

    def testException(self):
        self.setupStep(
            transfer.DirectoryUpload(slavesrc='srcdir', masterdest=self.destdir))

        behavior = UploadError(uploadTarFile('fake.tar', test="Hello world!"))

        self.expectCommands(
            Expect('uploadDirectory', dict(
                slavesrc="srcdir", workdir='wkdir',
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
            transfer.MultipleFileUpload(slavesrcs=[], masterdest=self.destdir))

        self.expectCommands()

        self.expectOutcome(result=SKIPPED, state_string="finished (skipped)")
        d = self.runStep()
        return d

    def testFile(self):
        self.setupStep(
            transfer.MultipleFileUpload(slavesrcs=["srcfile"], masterdest=self.destdir))

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

    def testDirectory(self):
        self.setupStep(
            transfer.MultipleFileUpload(slavesrcs=["srcdir"], masterdest=self.destdir))

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

    def testMultiple(self):
        self.setupStep(
            transfer.MultipleFileUpload(slavesrcs=["srcfile", "srcdir"], masterdest=self.destdir))

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
            transfer.MultipleFileUpload(slavesrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
                blocksize=16384, maxsize=None, keepstamp=False,
                writer=ExpectRemoteRef(remotetransfer.FileWriter)))
            + 1)

        self.expectOutcome(
            result=FAILURE, state_string="uploading 2 files (failure)")
        d = self.runStep()
        return d

    def testException(self):
        self.setupStep(
            transfer.MultipleFileUpload(slavesrcs=["srcfile", "srcdir"], masterdest=self.destdir))

        behavior = UploadError(uploadString("Hello world!"))

        self.expectCommands(
            Expect('stat', dict(file="srcfile",
                                workdir='wkdir'))
            + Expect.update('stat', [stat.S_IFREG, 99, 99])
            + 0,
            Expect('uploadFile', dict(
                slavesrc="srcfile", workdir='wkdir',
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
            slavesrcs=["srcfile", "srcdir"], masterdest=self.destdir)
        self.setupStep(step)

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

        @d.addCallback
        def checkCalls(res):
            self.assertEquals(step.uploadDone.call_count, 2)
            self.assertEquals(step.uploadDone.call_args_list[0],
                              ((SUCCESS, 'srcfile', os.path.join(self.destdir, 'srcfile')), {}))
            self.assertEquals(step.uploadDone.call_args_list[1],
                              ((SUCCESS, 'srcdir', os.path.join(self.destdir, 'srcdir')), {}))
            self.assertEquals(step.allUploadsDone.call_count, 1)
            self.assertEquals(step.allUploadsDone.call_args_list[0],
                              ((SUCCESS, ['srcfile', 'srcdir'], self.destdir), {}))
            return res

        return d


class TestStringDownload(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    # check that ConfigErrors is raised on invalid 'mode' argument

    def testModeConfError(self):
        self.assertRaisesRegexp(
            config.ConfigErrors,
            "StringDownload step's mode must be an integer or None,"
            " got 'not-a-number'",
            transfer.StringDownload,
            "string", "file", mode="not-a-number")

    def testBasic(self):
        self.setupStep(transfer.StringDownload("Hello World", "hello.txt"))

        self.step.buildslave = Mock()
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

        self.expectOutcome(result=SUCCESS, state_string="downloading to hello.txt")
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            self.assertEquals(''.join(read), "Hello World")
        return d

    def testFailure(self):
        self.setupStep(transfer.StringDownload("Hello World", "hello.txt"))

        self.expectCommands(
            Expect('downloadFile', dict(
                slavedest="hello.txt", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader)))
            + 1)

        self.expectOutcome(result=FAILURE, state_string="downloading to hello.txt (failure)")
        return self.runStep()


class TestJSONStringDownload(steps.BuildStepMixin, unittest.TestCase):
    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testBasic(self):
        msg = dict(message="Hello World")
        self.setupStep(transfer.JSONStringDownload(msg, "hello.json"))

        self.step.buildslave = Mock()
        self.step.remote = Mock()

        # A place to store what gets read
        read = []

        self.expectCommands(
            Expect('downloadFile', dict(
                slavedest="hello.json", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader))
            )
            + Expect.behavior(downloadString(read.append))
            + 0)

        self.expectOutcome(result=SUCCESS, state_string="downloading to hello.json")
        d = self.runStep()

        @d.addCallback
        def checkCalls(res):
            self.assertEquals(''.join(read), '{"message": "Hello World"}')
        return d

    def testFailure(self):
        msg = dict(message="Hello World")
        self.setupStep(transfer.JSONStringDownload(msg, "hello.json"))

        self.expectCommands(
            Expect('downloadFile', dict(
                slavedest="hello.json", workdir='wkdir',
                blocksize=16384, maxsize=None, mode=None,
                reader=ExpectRemoteRef(remotetransfer.StringFileReader)))
            + 1)

        self.expectOutcome(result=FAILURE, state_string="downloading to hello.json (failure)")
        return self.runStep()


class TestJSONPropertiesDownload(unittest.TestCase):

    def testBasic(self):
        s = transfer.JSONPropertiesDownload("props.json")
        s.build = Mock()
        props = Properties()
        props.setProperty('key1', 'value1', 'test')
        s.build.getProperties.return_value = props
        s.build.getSlaveCommandVersion.return_value = 1
        ss = Mock()
        ss.asDict.return_value = dict(revision="12345")
        s.build.getSourceStamp.return_value = ss

        s.buildslave = Mock()
        s.remote = Mock()

        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'downloadFile':
                self.assertEquals(kwargs['slavedest'], 'props.json')
                reader = kwargs['reader']
                data = reader.remote_read(100)
                self.assertEquals(
                    data, json.dumps(dict(sourcestamp=ss.asDict(), properties={'key1': 'value1'})))
                break
        else:
            self.assert_(False, "No downloadFile command found")
