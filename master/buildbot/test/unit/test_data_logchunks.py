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

from buildbot.data import logchunks
from buildbot.data import resultspec
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from twisted.internet import defer
from twisted.trial import unittest


class LogChunkEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = logchunks.LogChunkEndpoint
    resourceTypeClass = logchunks.LogChunk

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Master(id=88),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, buildslaveid=13,
                         buildrequestid=82, number=3),
            fakedb.Step(id=50, buildid=13, number=9, name='make'),
            fakedb.Log(id=60, stepid=50, name='stdio', slug='stdio', type='s',
                       num_lines=7),
            fakedb.LogChunk(logid=60, first_line=0, last_line=1, compressed=0,
                content=textwrap.dedent("""\
                        line zero
                        line 1""")),
            fakedb.LogChunk(logid=60, first_line=2, last_line=4, compressed=0,
                content=textwrap.dedent("""\
                        line TWO
                        line 3
                        line 2**2""")),
            fakedb.LogChunk(logid=60, first_line=5, last_line=5, compressed=0,
                            content="another line"),
            fakedb.LogChunk(logid=60, first_line=6, last_line=6, compressed=0,
                            content="yet another line"),
            fakedb.Log(id=61, stepid=50, name='errors', slug='errors',
                       type='t', num_lines=100),
        ] + [
            fakedb.LogChunk(logid=61, first_line=i, last_line=i, compressed=0,
                            content="%08d" % i)
            for i in range(100)
        ] + [
            fakedb.Log(id=62, stepid=50, name='notes', slug='notes', type='t',
                       num_lines=0),
            # logid 62 is empty
        ])

    log60Lines = ['line zero', 'line 1', 'line TWO', 'line 3', 'line 2**2',
                  'another line', 'yet another line']
    log61Lines = ['%08d' % i for i in range(100)]

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def do_test_chunks(self, path, logid, expLines):
        # get the whole thing in one go
        logchunk = yield self.callGet(path)
        self.validateData(logchunk)
        expContent = '\n'.join(expLines) + '\n'
        self.assertEqual(logchunk,
                         {'logid': logid, 'firstline': 0, 'content': expContent})

        # line-by-line
        for i in range(len(expLines)):
            logchunk = yield self.callGet(path,
                                          resultSpec=resultspec.ResultSpec(offset=i, limit=1))
            self.validateData(logchunk)
            self.assertEqual(logchunk,
                             {'logid': logid, 'firstline': i, 'content': expLines[i] + '\n'})

        # half and half
        mid = len(expLines) / 2
        for f, l in (0, mid), (mid, len(expLines) - 1):
            logchunk = yield self.callGet(path,
                                          resultSpec=resultspec.ResultSpec(offset=f, limit=l - f + 1))
            self.validateData(logchunk)
            expContent = '\n'.join(expLines[f:l + 1]) + '\n'
            self.assertEqual(logchunk,
                             {'logid': logid, 'firstline': f, 'content': expContent})

        # truncated at EOF
        f, l = len(expLines) - 2, len(expLines) + 10
        logchunk = yield self.callGet(path,
                                      resultSpec=resultspec.ResultSpec(offset=f, limit=l - f + 1))
        self.validateData(logchunk)
        expContent = '\n'.join(expLines[-2:]) + '\n'
        self.assertEqual(logchunk,
                         {'logid': logid, 'firstline': f, 'content': expContent})

        # some illegal stuff
        self.assertEqual(
            (yield self.callGet(path,
                                resultSpec=resultspec.ResultSpec(offset=-1))), None)
        self.assertEqual(
            (yield self.callGet(path,
                                resultSpec=resultspec.ResultSpec(offset=10, limit=-1))),
            None)

    def test_get_logid_60(self):
        return self.do_test_chunks(('log', 60, 'content'), 60,
                                   self.log60Lines)

    def test_get_logid_61(self):
        return self.do_test_chunks(('log', 61, 'content'), 61,
                                   self.log61Lines)

    @defer.inlineCallbacks
    def test_get_missing(self):
        logchunk = yield self.callGet(('log', 99, 'content'))
        self.assertEqual(logchunk, None)

    @defer.inlineCallbacks
    def test_get_empty(self):
        logchunk = yield self.callGet(('log', 62, 'content'))
        self.validateData(logchunk)
        self.assertEqual(logchunk['content'], '')

    @defer.inlineCallbacks
    def test_get_by_stepid(self):
        logchunk = yield self.callGet(
            ('step', 50, 'log', 'errors', 'content'))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 61)

    @defer.inlineCallbacks
    def test_get_by_buildid(self):
        logchunk = yield self.callGet(
            ('build', 13, 'step', 9, 'log', 'stdio', 'content'))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 60)

    @defer.inlineCallbacks
    def test_get_by_builder(self):
        logchunk = yield self.callGet(
            ('builder', 77, 'build', 3, 'step', 9,
             'log', 'errors', 'content'))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 61)

    @defer.inlineCallbacks
    def test_get_by_builder_step_name(self):
        logchunk = yield self.callGet(
            ('builder', 77, 'build', 3, 'step', 'make',
             'log', 'errors', 'content'))
        self.validateData(logchunk)
        self.assertEqual(logchunk['logid'], 61)


class LogChunk(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
        self.rtype = logchunks.LogChunk(self.master)

    def do_test_callthrough(self, dbMethodName, method, exp_args=None,
                            exp_kwargs=None, *args, **kwargs):
        rv = defer.succeed(None)
        m = mock.Mock(return_value=rv)
        setattr(self.master.db.logs, dbMethodName, m)
        self.assertIdentical(method(*args, **kwargs), rv)
        m.assert_called_with(*(exp_args or args), **(exp_kwargs or kwargs))

    def test_signature_appendLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.appendLog,  # fake
            self.rtype.appendLog)  # real
        def appendLog(self, logid, content):
            pass

    def test_appendLog(self):
        self.do_test_callthrough('appendLog',
                                 self.rtype.appendLog,
                                 logid=10, content=u'foo\nbar\n')
