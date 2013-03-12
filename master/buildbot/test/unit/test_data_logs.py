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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.data import logs, base
from buildbot.test.util import validation, endpoint, interfaces
from buildbot.test.fake import fakemaster, fakedb

class Log(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = logs.LogEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, slaveid=-1,
                    buildrequestid=82, number=3),
            fakedb.Step(id=50, buildid=13, number=5, name='make'),
            fakedb.Log(id=60, stepid=50, name=u'stdio', type='s'),
            fakedb.Log(id=61, stepid=50, name=u'errors', type='t'),
        ])


    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        log = yield self.callGet(dict(), dict(logid=60))
        validation.verifyData(self, 'log', {}, log)
        self.assertEqual(log, {
            'logid': 60,
            'name': u'stdio',
            'step_link': base.Link(('step', '50')),
            'stepid': 50,
            'complete': False,
            'num_lines': 0,
            'type': u's',
            'link': base.Link(('log', '60'))})


    @defer.inlineCallbacks
    def test_get_missing(self):
        log = yield self.callGet(dict(), dict(logid=62))
        self.assertEqual(log, None)

    @defer.inlineCallbacks
    def test_get_by_stepid(self):
        log = yield self.callGet(dict(), dict(stepid=50, log_name='errors'))
        validation.verifyData(self, 'log', {}, log)
        self.assertEqual(log['name'], u'errors')

    @defer.inlineCallbacks
    def test_get_by_buildid(self):
        log = yield self.callGet(dict(),
                dict(buildid=13, step_number=5, log_name='errors'))
        validation.verifyData(self, 'log', {}, log)
        self.assertEqual(log['name'], u'errors')

    @defer.inlineCallbacks
    def test_get_by_builder(self):
        log = yield self.callGet(dict(),
                dict(builderid=77, build_number=3, step_number=5,
                     log_name='errors'))
        validation.verifyData(self, 'log', {}, log)
        self.assertEqual(log['name'], u'errors')

    @defer.inlineCallbacks
    def test_get_by_builder_step_name(self):
        log = yield self.callGet(dict(),
                dict(builderid=77, build_number=3, step_name='make',
                     log_name='errors'))
        validation.verifyData(self, 'log', {}, log)
        self.assertEqual(log['name'], u'errors')


class LogContent(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = logs.LogContentEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, slaveid=-1,
                    buildrequestid=82, number=3),
            fakedb.Step(id=50, buildid=13, number=9, name='make'),
            fakedb.Log(id=60, stepid=50, name='stdio', type='s', num_lines=7),
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
            fakedb.Log(id=61, stepid=50, name='errors', type='t',
                num_lines=100),
        ] + [
            fakedb.LogChunk(logid=61, first_line=i, last_line=i, compressed=0,
                content="%08d" % i)
            for i in range(100)
        ] + [
            fakedb.Log(id=62, stepid=50, name='notes', type='t', num_lines=0),
            # logid 62 is empty
        ])

    log60Lines = [ 'line zero', 'line 1', 'line TWO', 'line 3', 'line 2**2',
                   'another line', 'yet another line']
    log61Lines = [ '%08d' % i for i in range(100) ]

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def do_test_chunks(self, kwargs, logid, expLines):
        # get the whole thing in one go
        logchunk = yield self.callGet(dict(), kwargs)
        validation.verifyData(self, 'logchunk', {}, logchunk)
        expContent = '\n'.join(expLines) + '\n'
        self.assertEqual(logchunk,
            {'logid': logid, 'firstline': 0, 'content': expContent})

        # line-by-line
        for i in range(len(expLines)):
            logchunk = yield self.callGet(dict(firstline=i, lastline=i),
                                          kwargs)
            validation.verifyData(self, 'logchunk', {}, logchunk)
            self.assertEqual(logchunk,
                {'logid': logid, 'firstline': i, 'content': expLines[i]+'\n'})

        # half and half
        mid = len(expLines)/2
        for f, l in (0, mid), (mid, len(expLines)-1):
            logchunk = yield self.callGet(
                    dict(firstline=f, lastline=l), kwargs)
            validation.verifyData(self, 'logchunk', {}, logchunk)
            expContent = '\n'.join(expLines[f:l+1]) + '\n'
            self.assertEqual(logchunk,
                {'logid': logid, 'firstline': f, 'content': expContent})

        # truncated at EOF
        f, l = len(expLines)-2, len(expLines)+10
        logchunk = yield self.callGet(
            dict(firstline=f, lastline=l), kwargs)
        validation.verifyData(self, 'logchunk', {}, logchunk)
        expContent = '\n'.join(expLines[-2:]) + '\n'
        self.assertEqual(logchunk,
            {'logid': logid, 'firstline': f, 'content': expContent})

        # some illegal stuff
        self.assertEqual(
            (yield self.callGet(dict(firstline=-1), kwargs)), None)
        self.assertEqual(
            (yield self.callGet(dict(firstline=10, lastline=9), kwargs)), None)

    def test_get_logid_60(self):
        return self.do_test_chunks({'logid': 60}, 60, self.log60Lines)

    def test_get_logid_61(self):
        return self.do_test_chunks({'logid': 61}, 61, self.log61Lines)

    @defer.inlineCallbacks
    def test_get_missing(self):
        logchunk = yield self.callGet(dict(), dict(logid=99))
        self.assertEqual(logchunk, None)

    @defer.inlineCallbacks
    def test_get_empty(self):
        logchunk = yield self.callGet(dict(), dict(logid=62))
        validation.verifyData(self, 'logchunk', {}, logchunk)
        self.assertEqual(logchunk['content'], '')

    @defer.inlineCallbacks
    def test_get_by_stepid(self):
        logchunk = yield self.callGet(
                dict(), dict(stepid=50, log_name='errors'))
        validation.verifyData(self, 'logchunk', {}, logchunk)
        self.assertEqual(logchunk['logid'], 61)

    @defer.inlineCallbacks
    def test_get_by_buildid(self):
        logchunk = yield self.callGet(dict(),
                dict(buildid=13, step_number=9, log_name='stdio'))
        validation.verifyData(self, 'logchunk', {}, logchunk)
        self.assertEqual(logchunk['logid'], 60)

    @defer.inlineCallbacks
    def test_get_by_builder(self):
        logchunk = yield self.callGet(dict(),
                dict(builderid=77, build_number=3, step_number=9,
                     log_name='errors'))
        validation.verifyData(self, 'logchunk', {}, logchunk)
        self.assertEqual(logchunk['logid'], 61)

    @defer.inlineCallbacks
    def test_get_by_builder_step_name(self):
        logchunk = yield self.callGet(dict(),
                dict(builderid=77, build_number=3, step_name='make',
                     log_name='errors'))
        validation.verifyData(self, 'logchunk', {}, logchunk)
        self.assertEqual(logchunk['logid'], 61)


class Logs(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = logs.LogsEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, slaveid=-1,
                    buildrequestid=82, number=3),
            fakedb.Step(id=50, buildid=13, number=9, name='make'),
            fakedb.Log(id=60, stepid=50, name='stdio', type='s'),
            fakedb.Log(id=61, stepid=50, name='errors', type='t'),
            fakedb.Step(id=51, buildid=13, number=10, name='make_install'),
            fakedb.Log(id=70, stepid=51, name='stdio', type='s'),
            fakedb.Log(id=71, stepid=51, name='results_html', type='h'),
            fakedb.Step(id=52, buildid=13, number=11, name='nothing'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_stepid(self):
        logs = yield self.callGet(dict(), dict(stepid=50))
        [ validation.verifyData(self, 'log', {}, log)
          for log in logs ]
        self.assertEqual(sorted([ b['name'] for b in logs ]),
                         ['errors', 'stdio'])

    @defer.inlineCallbacks
    def test_get_stepid_empty(self):
        logs = yield self.callGet(dict(), dict(stepid=52))
        self.assertEqual(logs, [])

    @defer.inlineCallbacks
    def test_get_stepid_missing(self):
        logs = yield self.callGet(dict(), dict(stepid=99))
        self.assertEqual(logs, [])

    @defer.inlineCallbacks
    def test_get_buildid_step_name(self):
        logs = yield self.callGet(dict(),
                dict(buildid=13, step_name='make_install'))
        [ validation.verifyData(self, 'log', {}, log)
          for log in logs ]
        self.assertEqual(sorted([ b['name'] for b in logs ]),
                         ['results_html', 'stdio'])

    @defer.inlineCallbacks
    def test_get_buildid_step_number(self):
        logs = yield self.callGet(dict(),
                dict(buildid=13, step_number=10))
        [ validation.verifyData(self, 'log', {}, log)
          for log in logs ]
        self.assertEqual(sorted([ b['name'] for b in logs ]),
                         ['results_html', 'stdio'])

    @defer.inlineCallbacks
    def test_get_builder_build_number_step_name(self):
        logs = yield self.callGet(dict(),
                dict(builderid=77, build_number=3, step_name='make'))
        [ validation.verifyData(self, 'log', {}, log)
          for log in logs ]
        self.assertEqual(sorted([ b['name'] for b in logs ]),
                         ['errors', 'stdio'])

    @defer.inlineCallbacks
    def test_get_builder_build_number_step_number(self):
        logs = yield self.callGet(dict(),
                dict(builderid=77, build_number=3, step_number=10))
        [ validation.verifyData(self, 'log', {}, log)
          for log in logs ]
        self.assertEqual(sorted([ b['name'] for b in logs ]),
                         ['results_html', 'stdio'])


class BuildResourceType(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                wantMq=True, wantDb=True, wantData=True)
        self.rtype = logs.LogsResourceType(self.master)

    def do_test_callthrough(self, dbMethodName, method, exp_args=None,
            exp_kwargs=None, *args, **kwargs):
        rv = defer.succeed(None)
        m = mock.Mock(return_value=rv)
        setattr(self.master.db.logs, dbMethodName, m)
        self.assertIdentical(method(*args, **kwargs), rv)
        m.assert_called_with(*(exp_args or args), **(exp_kwargs or kwargs))

    def test_signature_newLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.newLog, # fake
            self.rtype.newLog) # real
        def newLog(self, stepid, name, type):
            pass

    def test_newLog(self):
        self.do_test_callthrough('addLog', self.rtype.newLog,
                stepid=203, name='stdio', type='s')

    def test_signature_finishLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.finishLog, # fake
            self.rtype.finishLog) # real
        def finishLog(self, logid):
            pass

    def test_finishLog(self):
        self.do_test_callthrough('finishLog', self.rtype.finishLog,
                logid=10)

    def test_signature_compressLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.compressLog, # fake
            self.rtype.compressLog) # real
        def compressLog(self, logid):
            pass

    def test_compressLog(self):
        self.do_test_callthrough('compressLog',
                self.rtype.compressLog,
                logid=10)

    def test_signature_appendLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.appendLog, # fake
            self.rtype.appendLog) # real
        def appendLog(self, logid, content):
            pass

    def test_appendLog(self):
        self.do_test_callthrough('appendLog',
                self.rtype.appendLog,
                logid=10, content=u'foo\nbar\n')
