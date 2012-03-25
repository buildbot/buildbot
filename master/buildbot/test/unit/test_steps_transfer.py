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

from __future__ import with_statement

import tempfile, os
import shutil
import tarfile
from twisted.trial import unittest

from mock import Mock

from buildbot.process.properties import Properties
from buildbot.util import json
from buildbot.steps import transfer
from buildbot.status.results import SUCCESS
from buildbot import config
from buildbot.test.util import steps
from buildbot.test.fake.remotecommand import Expect, ExpectRemoteRef

class TestFileUpload(unittest.TestCase):
    def setUp(self):
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)

    def tearDown(self):
        if os.path.exists(self.destfile):
            os.unlink(self.destfile)

    def test_constructor_mode_type(self):
        self.assertRaises(config.ConfigErrors, lambda :
                transfer.FileUpload(slavesrc=__file__, masterdest='xyz', mode='g+rwx'))

    def testBasic(self):
        s = transfer.FileUpload(slavesrc=__file__, masterdest=self.destfile)
        s.build = Mock()
        s.build.getProperties.return_value = Properties()
        s.build.getSlaveCommandVersion.return_value = 1

        s.step_status = Mock()
        s.buildslave = Mock()
        s.remote = Mock()

        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'uploadFile':
                self.assertEquals(kwargs['slavesrc'], __file__)
                writer = kwargs['writer']
                with open(__file__, "rb") as f:
                    writer.remote_write(f.read())
                self.assert_(not os.path.exists(self.destfile))
                writer.remote_close()
                break
        else:
            self.assert_(False, "No uploadFile command found")

        with open(self.destfile, "rb") as dest:
            with open(__file__, "rb") as expect:
                self.assertEquals(dest.read(), expect.read())

    def testTimestamp(self):
        s = transfer.FileUpload(slavesrc=__file__, masterdest=self.destfile, keepstamp=True)
        s.build = Mock()
        s.build.getProperties.return_value = Properties()
        s.build.getSlaveCommandVersion.return_value = "2.13"

        s.step_status = Mock()
        s.buildslave = Mock()
        s.remote = Mock()
        s.start()
        timestamp = ( os.path.getatime(__file__),
                      os.path.getmtime(__file__) )

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'uploadFile':
                self.assertEquals(kwargs['slavesrc'], __file__)
                writer = kwargs['writer']
                with open(__file__, "rb") as f:
                    writer.remote_write(f.read())
                self.assert_(not os.path.exists(self.destfile))
                writer.remote_close()
                writer.remote_utime(timestamp)
                break
        else:
            self.assert_(False, "No uploadFile command found")

        desttimestamp = ( os.path.getatime(self.destfile),
                          os.path.getmtime(self.destfile) )

        timestamp = map(int, timestamp)
        desttimestamp = map(int, desttimestamp)

        self.assertEquals(timestamp[0],desttimestamp[0])
        self.assertEquals(timestamp[1],desttimestamp[1])

    def testURL(self):
        s = transfer.FileUpload(slavesrc=__file__, masterdest=self.destfile, url="http://server/file")
        s.build = Mock()
        s.build.getProperties.return_value = Properties()
        s.build.getSlaveCommandVersion.return_value = "2.13"

        s.step_status = Mock()
        s.step_status.addURL = Mock()
        s.buildslave = Mock()
        s.remote = Mock()
        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'uploadFile':
                self.assertEquals(kwargs['slavesrc'], __file__)
                writer = kwargs['writer']
                with open(__file__, "rb") as f:
                    writer.remote_write(f.read())
                self.assert_(not os.path.exists(self.destfile))
                writer.remote_close()
                break
        else:
            self.assert_(False, "No uploadFile command found")

        s.step_status.addURL.assert_called_once_with(
            os.path.basename(self.destfile), "http://server/file")

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

        def upload_behavior(command):
            from cStringIO import StringIO
            f = StringIO()
            archive = tarfile.TarFile(fileobj=f, name='fake.tar', mode='w')
            archive.addfile(tarfile.TarInfo("test"), StringIO("Hello World!"))
            writer = command.args['writer']
            writer.remote_write(f.getvalue())
            writer.remote_unpack()

        self.expectCommands(
            Expect('uploadDirectory', dict(
                slavesrc="srcdir", workdir='wkdir',
                blocksize=16384, compress=None, maxsize=None,
                writer=ExpectRemoteRef(transfer._DirectoryWriter)))
            + Expect.behavior(upload_behavior)
            + 0)

        self.expectOutcome(result=SUCCESS, status_text=["uploading", "srcdir"])
        d = self.runStep()
        return d

class TestStringDownload(unittest.TestCase):
    def testBasic(self):
        s = transfer.StringDownload("Hello World", "hello.txt")
        s.build = Mock()
        s.build.getProperties.return_value = Properties()
        s.build.getSlaveCommandVersion.return_value = 1

        s.step_status = Mock()
        s.buildslave = Mock()
        s.remote = Mock()

        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'downloadFile':
                self.assertEquals(kwargs['slavedest'], 'hello.txt')
                reader = kwargs['reader']
                data = reader.remote_read(100)
                self.assertEquals(data, "Hello World")
                break
        else:
            self.assert_(False, "No downloadFile command found")

class TestJSONStringDownload(unittest.TestCase):
    def testBasic(self):
        msg = dict(message="Hello World")
        s = transfer.JSONStringDownload(msg, "hello.json")
        s.build = Mock()
        s.build.getProperties.return_value = Properties()
        s.build.getSlaveCommandVersion.return_value = 1

        s.step_status = Mock()
        s.buildslave = Mock()
        s.remote = Mock()

        s.start()

        for c in s.remote.method_calls:
            name, command, args = c
            commandName = command[3]
            kwargs = command[-1]
            if commandName == 'downloadFile':
                self.assertEquals(kwargs['slavedest'], 'hello.json')
                reader = kwargs['reader']
                data = reader.remote_read(100)
                self.assertEquals(data, json.dumps(msg))
                break
        else:
            self.assert_(False, "No downloadFile command found")

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

        s.step_status = Mock()
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
                self.assertEquals(data, json.dumps(dict(sourcestamp=ss.asDict(), properties={'key1': 'value1'})))
                break
        else:
            self.assert_(False, "No downloadFile command found")
