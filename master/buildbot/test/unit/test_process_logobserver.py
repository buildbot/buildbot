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

from twisted.trial import unittest
from twisted.internet import defer
from buildbot.process import log
from buildbot.process import logobserver
from buildbot.test.fake import fakemaster

class MyLogObserver(logobserver.LogObserver):

    def __init__(self):
        self.obs = []

    def outReceived(self, data):
        self.obs.append(('out', data))

    def errReceived(self, data):
        self.obs.append(('err', data))

    def finishReceived(self):
        self.obs.append(('fin',))


class TestLogObserver(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantData=True)

    @defer.inlineCallbacks
    def test_sequence(self):
        logid = yield self.master.data.updates.newLog(1, u'mine', u's')
        l = log.Log.new(self.master, 'mine', 's', logid)
        lo = MyLogObserver()
        lo.setLog(l)

        yield l.addStdout(u'hello\n')
        yield l.addStderr(u'cruel\n')
        yield l.addStdout(u'world\n')
        yield l.addStdout(u'multi\nline\nchunk\n')
        yield l.finish()

        self.assertEqual(lo.obs, [
            ('out', 'hello\n'),
            ('err', 'cruel\n'),
            ('out', 'world\n'),
            ('out', 'multi\nline\nchunk\n'),
            ('fin',),
        ])


class MyLogLineObserver(logobserver.LogLineObserver):

    def __init__(self):
        logobserver.LogLineObserver.__init__(self)
        self.obs = []

    def outLineReceived(self, data):
        self.obs.append(('out', data))

    def errLineReceived(self, data):
        self.obs.append(('err', data))

    def finishReceived(self):
        self.obs.append(('fin',))


class TestLogLineObserver(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantData=True)

    @defer.inlineCallbacks
    def test_sequence(self):
        logid = yield self.master.data.updates.newLog(1, u'mine', u's')
        l = log.Log.new(self.master, 'mine', 's', logid)
        lo = MyLogLineObserver()
        lo.setLog(l)

        yield l.addStdout(u'hello\n')
        yield l.addStderr(u'cruel\n')
        yield l.addStdout(u'multi\nline\nchunk\n')
        yield l.finish()

        self.assertEqual(lo.obs, [
            ('out', 'hello'),
            ('err', 'cruel'),
            ('out', 'multi'),
            ('out', 'line'),
            ('out', 'chunk'),
            ('fin',),
        ])

    def test_old_setMaxLineLength(self):
        # this method is gone, but used to be documented, so it's stil
        # callable.  Just don't fail.
        lo = MyLogLineObserver()
        lo.setMaxLineLength(120939403)
