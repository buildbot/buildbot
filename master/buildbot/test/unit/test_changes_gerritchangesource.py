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
# this program; if not, write to the Free Software Foundation, Inc[''], 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

import datetime
import json
import types

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

from buildbot.changes import gerritchangesource
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakedb
from buildbot.test.fake.change import Change
from buildbot.test.util import changesource


class TestGerritHelpers(unittest.TestCase):

    def test_proper_json(self):
        self.assertEqual(u"Justin Case <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase",
                             "name": "Justin Case",
                             "email": "justin.case@example.com"
                         }))

    def test_missing_username(self):
        self.assertEqual(u"Justin Case <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "name": "Justin Case",
                             "email": "justin.case@example.com"
                         }))

    def test_missing_name(self):
        self.assertEqual(u"unknown <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "email": "justin.case@example.com"
                         }))
        self.assertEqual(u"gerrit <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "email": "justin.case@example.com"
                         }, u"gerrit"))
        self.assertEqual(u"justincase <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase",
                             "email": "justin.case@example.com"
                         }, u"gerrit"))

    def test_missing_email(self):
        self.assertEqual(u"Justin Case",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase",
                             "name": "Justin Case"
                         }))
        self.assertEqual(u"Justin Case",
                         gerritchangesource._gerrit_user_to_author({
                             "name": "Justin Case"
                         }))
        self.assertEqual(u"justincase",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase"
                         }))
        self.assertEqual(u"unknown",
                         gerritchangesource._gerrit_user_to_author({
                         }))
        self.assertEqual(u"gerrit",
                         gerritchangesource._gerrit_user_to_author({
                         }, u"gerrit"))


class TestGerritChangeSource(changesource.ChangeSourceMixin,
                             unittest.TestCase):

    def setUp(self):
        return self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    def newChangeSource(self, host, user, *args, **kwargs):
        s = gerritchangesource.GerritChangeSource(
            host, user, *args, **kwargs)
        self.attachChangeSource(s)
        s.configureService()
        return s

    # tests

    def test_describe(self):
        s = self.newChangeSource('somehost', 'someuser')
        self.assertSubstring("GerritChangeSource", s.describe())

    def test_name(self):
        s = self.newChangeSource('somehost', 'someuser')
        self.assertEqual("GerritChangeSource:someuser@somehost:29418", s.name)

        s = self.newChangeSource('somehost', 'someuser', name="MyName")
        self.assertEqual("MyName", s.name)

    # TODO: test the backoff algorithm

    # this variable is reused in test_steps_source_repo
    # to ensure correct integration between change source and repo step
    expected_change = {'category': u'patchset-created',
                       'files': ['unknown'],
                       'repository': u'ssh://someuser@somehost:29418/pr',
                       'author': u'Dustin <dustin@mozilla.com>',
                       'comments': u'fix 1234',
                       'project': u'pr',
                       'branch': u'br/4321',
                       'revlink': u'http://buildbot.net',
                       'codebase': None,
                       'revision': u'abcdef',
                       'src': None,
                       'when_timestamp': None,
                       'properties': {u'event.change.owner.email': u'dustin@mozilla.com',
                                      u'event.change.subject': u'fix 1234',
                                      u'event.change.project': u'pr',
                                      u'event.change.owner.name': u'Dustin',
                                      u'event.change.number': u'4321',
                                      u'event.change.url': u'http://buildbot.net',
                                      u'event.change.branch': u'br',
                                      u'event.type': u'patchset-created',
                                      u'event.patchSet.revision': u'abcdef',
                                      u'event.patchSet.number': u'12'}}

    def test_lineReceived_patchset_created(self):
        s = self.newChangeSource('somehost', 'someuser')
        d = s.lineReceived(json.dumps(dict(
            type="patchset-created",
            change=dict(
                branch="br",
                project="pr",
                number="4321",
                owner=dict(name="Dustin", email="dustin@mozilla.com"),
                url="http://buildbot.net",
                subject="fix 1234"
            ),
            patchSet=dict(revision="abcdef", number="12")
        )))

        @d.addCallback
        def check(_):
            self.assertEqual(len(self.master.data.updates.changesAdded), 1)
            c = self.master.data.updates.changesAdded[0]
            for k, v in iteritems(c):
                self.assertEqual(self.expected_change[k], v)
        return d

    change_merged_event = {
        "type": "change-merged",
        "change": {
            "branch": "br",
            "project": "pr",
            "number": "4321",
            "owner": {"name": "Chuck", "email": "chuck@norris.com"},
            "url": "http://buildbot.net",
            "subject": "fix 1234"},
        "patchSet": {"revision": "abcdefj", "number": "13"}
    }

    def test_handled_events_filter_true(self):
        s = self.newChangeSource(
            'somehost', 'some_choosy_user', handled_events=["change-merged"])
        d = s.lineReceived(json.dumps(self.change_merged_event))

        @d.addCallback
        def check(_):
            self.assertEqual(len(self.master.data.updates.changesAdded), 1)
            c = self.master.data.updates.changesAdded[0]
            self.assertEqual(c["category"], "change-merged")
            self.assertEqual(c["branch"], "br")
        return d

    def test_handled_events_filter_false(self):
        s = self.newChangeSource(
            'somehost', 'some_choosy_user')
        d = s.lineReceived(json.dumps(self.change_merged_event))

        @d.addCallback
        def check(_):
            self.assertEqual(len(self.master.data.updates.changesAdded), 0)
        return d

    def test_custom_handler(self):
        s = self.newChangeSource(
            'somehost', 'some_choosy_user',
            handled_events=["change-merged"])

        def custom_handler(self, properties, event):
            event['change']['project'] = "world"
            return self.addChangeFromEvent(properties, event)
        # Patches class to not bother with the inheritance
        s.eventReceived_change_merged = types.MethodType(custom_handler, s)
        d = s.lineReceived(json.dumps(self.change_merged_event))

        @d.addCallback
        def check(_):
            self.assertEqual(len(self.master.data.updates.changesAdded), 1)
            c = self.master.data.updates.changesAdded[0]
            self.assertEqual(c['project'], "world")
        return d

    def test_startStreamProcess_bytes_output(self):
        s = self.newChangeSource(
            'somehost', 'some_choosy_user', debug=True)

        exp_argv = ['ssh', 'some_choosy_user@somehost', '-p', '29418']
        exp_argv += ['gerrit', 'stream-events']

        def spawnProcess(pp, cmd, argv, env):
            self.assertEqual([cmd, argv], [exp_argv[0], exp_argv])
            pp.errReceived(b'test stderr\n')
            pp.outReceived(b'{"type":"dropped-output"}\n')
            so = error.ProcessDone(None)
            pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)

        s.startStreamProcess()


class TestGerritEventLogPoller(changesource.ChangeSourceMixin,
                               unittest.TestCase):
    NOW_TIMESTAMP = 1479302598
    EVENT_TIMESTAMP = 1479302599
    NOW_FORMATTED = '2016-16-11 13:23:18'
    EVENT_FORMATTED = '2016-16-11 13:23:19'
    OBJECTID = 1234

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpChangeSource()
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        yield self.tearDownChangeSource()

    @defer.inlineCallbacks
    def newChangeSource(self, **kwargs):
        auth = kwargs.pop('auth', ('log', 'pass'))
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'gerrit', auth=auth)
        self.changesource = gerritchangesource.GerritEventLogPoller(
            'gerrit', auth=auth, gitBaseURL="ssh://someuser@somehost:29418", pollAtLaunch=False, **kwargs)

    @defer.inlineCallbacks
    def startChangeSource(self):
        yield self.changesource.setServiceParent(self.master)
        yield self.attachChangeSource(self.changesource)

    # tests
    @defer.inlineCallbacks
    def test_now(self):
        yield self.newChangeSource()
        self.changesource.now()

    @defer.inlineCallbacks
    def test_describe(self):
        # describe is not used yet in buildbot nine, but it can still be useful in the future, so lets
        # implement and test it
        yield self.newChangeSource()
        self.assertSubstring('GerritEventLogPoller', self.changesource.describe())

    @defer.inlineCallbacks
    def test_name(self):
        yield self.newChangeSource()
        self.assertEqual('GerritEventLogPoller:gerrit', self.changesource.name)

    @defer.inlineCallbacks
    def test_lineReceived_patchset_created(self):
        self.master.db.insertTestData([
            fakedb.Object(id=self.OBJECTID, name='GerritEventLogPoller:gerrit',
                          class_name='GerritEventLogPoller')])
        yield self.newChangeSource()
        self.changesource.now = lambda: datetime.datetime.utcfromtimestamp(self.NOW_TIMESTAMP)
        self._http.expect(method='get', ep='/plugins/events-log/events/',
                          params={'t1': self.NOW_FORMATTED},
                          content_json=dict(
                              type="patchset-created",
                              change=dict(
                                  branch="br",
                                  project="pr",
                                  number="4321",
                                  owner=dict(name="Dustin", email="dustin@mozilla.com"),
                                  url="http://buildbot.net",
                                  subject="fix 1234"
                              ),
                              eventCreatedOn=self.EVENT_TIMESTAMP,
                              patchSet=dict(revision="abcdef", number="12")))

        yield self.startChangeSource()
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        c = self.master.data.updates.changesAdded[0]
        for k, v in iteritems(c):
            self.assertEqual(TestGerritChangeSource.expected_change[k], v)
        self.master.db.state.assertState(self.OBJECTID, last_event_ts=self.EVENT_TIMESTAMP)

        # do a second poll, it should ask for the next events
        self._http.expect(method='get', ep='/plugins/events-log/events/',
                          params={'t1': self.EVENT_FORMATTED},
                          content_json=dict(
                              type="patchset-created",
                              change=dict(
                                  branch="br",
                                  project="pr",
                                  number="4321",
                                  owner=dict(name="Dustin", email="dustin@mozilla.com"),
                                  url="http://buildbot.net",
                                  subject="fix 1234"
                              ),
                              eventCreatedOn=self.EVENT_TIMESTAMP + 1,
                              patchSet=dict(revision="abcdef", number="12")))

        yield self.changesource.poll()
        self.master.db.state.assertState(self.OBJECTID, last_event_ts=self.EVENT_TIMESTAMP + 1)


class TestGerritChangeFilter(unittest.TestCase):

    def test_basic(self):

        ch = Change(**TestGerritChangeSource.expected_change)
        f = gerritchangesource.GerritChangeFilter(
            branch=["br"], eventtype=["patchset-created"])
        self.assertTrue(f.filter_change(ch))
        f = gerritchangesource.GerritChangeFilter(
            branch="br2", eventtype=["patchset-created"])
        self.assertFalse(f.filter_change(ch))
        f = gerritchangesource.GerritChangeFilter(
            branch="br", eventtype="ref-updated")
        self.assertFalse(f.filter_change(ch))
        self.assertEqual(
            repr(f),
            '<GerritChangeFilter on prop:event.change.branch == br and prop:event.type == ref-updated>')
