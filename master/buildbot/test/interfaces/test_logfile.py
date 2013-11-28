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

import mock
import textwrap

from buildbot.status import logfile
from buildbot.test.fake import remotecommand
from buildbot.test.util import dirs
from buildbot.test.util import interfaces
from twisted.trial import unittest

# NOTE:
#
# This interface is considered private to Buildbot and may change without
# warning in future versions.


class Tests(interfaces.InterfaceTests):

    def makeLogFile(self, name='n', logfilename='nLog'):
        raise NotImplementedError

    def addLogData(self, log):
        log.addStdout('some text with\nembedded newlines\n')
        log.addStdout('no newlines - ')
        log.addHeader("won't see this\n")
        log.addStdout('newlines\n')
        log.addStderr('also hidden')

    # tests

    def test_signature_getName(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.getName)
        def getName(self):
            pass

    def test_signature_addHeader(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.addHeader)
        def addHeader(self, text):
            pass

    def test_signature_addStdout(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.addStdout)
        def addStdout(self, text):
            pass

    def test_signature_addStderr(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.addStderr)
        def addStderr(self, text):
            pass

    def test_signature_readlines(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.readlines)
        def readlines(self):
            pass

    def test_signature_getText(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.getText)
        def getText(self):
            pass

    def test_signature_getChunks(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.getChunks)
        def getChunks(self, channels=[], onlyText=False):
            pass

    def test_signature_finish(self):
        log = self.makeLogFile()

        @self.assertArgSpecMatches(log.finish)
        def finish(self):
            pass

    def test_readlines(self):
        log = self.makeLogFile()
        self.addLogData(log)
        self.assertEqual(list(log.readlines()), [
            'some text with\n',
            'embedded newlines\n',
            'no newlines - newlines\n'
            ''
        ])

    def test_getText(self):
        log = self.makeLogFile()
        self.addLogData(log)
        self.assertEqual(log.getText(), textwrap.dedent("""\
            some text with
            embedded newlines
            no newlines - newlines
            also hidden"""))


class RealTests(Tests):

    def test_getTextWithHeaders(self):
        log = self.makeLogFile()
        self.addLogData(log)
        self.assertEqual(log.getTextWithHeaders(), textwrap.dedent("""\
            some text with
            embedded newlines
            no newlines - won't see this
            newlines
            also hidden"""))


class TestLogFile(unittest.TestCase, dirs.DirsMixin, RealTests):

    def setUp(self):
        self.setUpDirs('basedir')

    def tearDown(self):
        self.tearDownDirs()

    def makeLogFile(self, name='n', logfilename='nLog'):
        # this is one reason this interface sucks:
        parent = mock.Mock(name='fake StepStatus')
        parent.build.builder.basedir = 'basedir'
        return logfile.LogFile(parent, name, logfilename)


class TestFakeLogFile(unittest.TestCase, Tests):

    def makeLogFile(self, name='n', logfilename='nLog'):
        step = mock.Mock(name='fake step')
        step.logobservers = []
        return remotecommand.FakeLogFile(name, step)
