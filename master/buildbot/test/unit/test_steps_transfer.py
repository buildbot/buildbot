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

import tempfile, os
from twisted.trial import unittest

from mock import Mock

from buildbot.process.properties import Properties
from buildbot.util import json
from buildbot.steps.transfer import StringDownload, JSONStringDownload, JSONPropertiesDownload, \
    FileUpload

class TestFileUpload(unittest.TestCase):
    def setUp(self):
        fd, self.destfile = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.destfile)

    def tearDown(self):
        os.unlink(self.destfile)

    def testBasic(self):
        s = FileUpload(slavesrc=__file__, masterdest=self.destfile)
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
                writer.remote_write(open(__file__, "rb").read())
                self.assert_(not os.path.exists(self.destfile))
                writer.remote_close()
                break
        else:
            self.assert_(False, "No uploadFile command found")

        self.assertEquals(open(self.destfile, "rb").read(),
                open(__file__, "rb").read())

    def testTimestamp(self):
        s = FileUpload(slavesrc=__file__, masterdest=self.destfile, keepstamp=True)
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
                writer.remote_write(open(__file__, "rb").read())
                self.assert_(not os.path.exists(self.destfile))
                writer.remote_close()
                writer.remote_utime(timestamp)
                break
        else:
            self.assert_(False, "No uploadFile command found")

        desttimestamp = ( os.path.getatime(self.destfile),
                          os.path.getmtime(self.destfile) )
        self.assertAlmostEquals(timestamp[0],desttimestamp[0],places=5)
        self.assertAlmostEquals(timestamp[1],desttimestamp[1],places=5)

class TestStringDownload(unittest.TestCase):
    def testBasic(self):
        s = StringDownload("Hello World", "hello.txt")
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
        s = JSONStringDownload(msg, "hello.json")
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
        s = JSONPropertiesDownload("props.json")
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
