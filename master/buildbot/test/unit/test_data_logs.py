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


class LogResourceType(interfaces.InterfaceTests, unittest.TestCase):

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
