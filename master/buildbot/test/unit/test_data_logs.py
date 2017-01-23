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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import logs
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces


class LogEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = logs.LogEndpoint
    resourceTypeClass = logs.Log

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=3),
            fakedb.Step(id=50, buildid=13, number=5, name='make'),
            fakedb.Log(id=60, stepid=50, name=u'stdio',
                       slug=u'stdio', type='s'),
            fakedb.Log(id=61, stepid=50, name=u'errors',
                       slug=u'errors', type='t'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        log = yield self.callGet(('logs', 60))
        self.validateData(log)
        self.assertEqual(log, {
            'logid': 60,
            'name': u'stdio',
            'slug': u'stdio',
            'stepid': 50,
            'complete': False,
            'num_lines': 0,
            'type': u's'})

    @defer.inlineCallbacks
    def test_get_missing(self):
        log = yield self.callGet(('logs', 62))
        self.assertEqual(log, None)

    @defer.inlineCallbacks
    def test_get_by_stepid(self):
        log = yield self.callGet(('steps', 50, 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], u'errors')

    @defer.inlineCallbacks
    def test_get_by_buildid(self):
        log = yield self.callGet(('builds', 13, 'steps', 5, 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], u'errors')

    @defer.inlineCallbacks
    def test_get_by_builder(self):
        log = yield self.callGet(
            ('builders', '77', 'builds', 3, 'steps', 5, 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], u'errors')

    @defer.inlineCallbacks
    def test_get_by_builder_step_name(self):
        log = yield self.callGet(
            ('builders', '77', 'builds', 3, 'steps', 'make',
             'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], u'errors')


class LogsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = logs.LogsEndpoint
    resourceTypeClass = logs.Log

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, workerid=13,
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
        logs = yield self.callGet(('steps', 50, 'logs'))

        [self.validateData(log)
         for log in logs]
        self.assertEqual(sorted([b['name'] for b in logs]),
                         ['errors', 'stdio'])

    @defer.inlineCallbacks
    def test_get_stepid_empty(self):
        logs = yield self.callGet(('steps', 52, 'logs'))
        self.assertEqual(logs, [])

    @defer.inlineCallbacks
    def test_get_stepid_missing(self):
        logs = yield self.callGet(('steps', 99, 'logs'))
        self.assertEqual(logs, [])

    @defer.inlineCallbacks
    def test_get_buildid_step_name(self):
        logs = yield self.callGet(
            ('builds', 13, 'steps', 'make_install', 'logs'))
        [self.validateData(log)
         for log in logs]
        self.assertEqual(sorted([b['name'] for b in logs]),
                         ['results_html', 'stdio'])

    @defer.inlineCallbacks
    def test_get_buildid_step_number(self):
        logs = yield self.callGet(('builds', 13, 'steps', 10, 'logs'))
        [self.validateData(log)
         for log in logs]
        self.assertEqual(sorted([b['name'] for b in logs]),
                         ['results_html', 'stdio'])

    @defer.inlineCallbacks
    def test_get_builder_build_number_step_name(self):
        logs = yield self.callGet(
            ('builders', 77, 'builds', 3, 'steps', 'make', 'logs'))
        [self.validateData(log)
         for log in logs]
        self.assertEqual(sorted([b['name'] for b in logs]),
                         ['errors', 'stdio'])

    @defer.inlineCallbacks
    def test_get_builder_build_number_step_number(self):
        logs = yield self.callGet(
            ('builders', 77, 'builds', 3, 'steps', 10, 'logs'))
        [self.validateData(log)
         for log in logs]
        self.assertEqual(sorted([b['name'] for b in logs]),
                         ['results_html', 'stdio'])


class Log(interfaces.InterfaceTests, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
        self.rtype = logs.Log(self.master)

    @defer.inlineCallbacks
    def do_test_callthrough(self, dbMethodName, method, exp_args=None,
                            exp_kwargs=None, *args, **kwargs):
        rv = (1, 2)
        m = mock.Mock(return_value=defer.succeed(rv))
        setattr(self.master.db.logs, dbMethodName, m)
        res = yield method(*args, **kwargs)
        self.assertIdentical(res, rv)
        m.assert_called_with(*(exp_args or args), **(exp_kwargs or kwargs))

    def test_signature_newLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.addLog,  # fake
            self.rtype.addLog)  # real
        def newLog(self, stepid, name, type):
            pass

    @defer.inlineCallbacks
    def test_newLog_uniquify(self):
        tries = []

        @self.assertArgSpecMatches(self.master.db.logs.addLog)
        def addLog(stepid, name, slug, type):
            tries.append((stepid, name, slug, type))
            if len(tries) < 3:
                return defer.fail(KeyError())
            return defer.succeed(23)
        self.patch(self.master.db.logs, 'addLog', addLog)
        logid = yield self.rtype.addLog(
            stepid=13, name=u'foo', type=u's')
        self.assertEqual(logid, 23)
        self.assertEqual(tries, [
            (13, u'foo', u'foo', 's'),
            (13, u'foo', u'foo_2', 's'),
            (13, u'foo', u'foo_3', 's'),
        ])

    def test_signature_finishLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.finishLog,  # fake
            self.rtype.finishLog)  # real
        def finishLog(self, logid):
            pass

    def test_finishLog(self):
        self.do_test_callthrough('finishLog', self.rtype.finishLog,
                                 logid=10)

    def test_signature_compressLog(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.compressLog,  # fake
            self.rtype.compressLog)  # real
        def compressLog(self, logid):
            pass

    def test_compressLog(self):
        self.do_test_callthrough('compressLog',
                                 self.rtype.compressLog,
                                 logid=10)

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
