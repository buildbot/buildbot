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

import datetime
import json
import types

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet import utils
from twisted.python import failure
from twisted.trial import unittest

from buildbot.changes import gerritchangesource
from buildbot.test.fake import fakedb
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.change import Change
from buildbot.test.util import changesource
from buildbot.test.util.misc import TestReactorMixin


class TestGerritHelpers(unittest.TestCase):

    def test_proper_json(self):
        self.assertEqual("Justin Case <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase",
                             "name": "Justin Case",
                             "email": "justin.case@example.com"
                         }))

    def test_missing_username(self):
        self.assertEqual("Justin Case <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "name": "Justin Case",
                             "email": "justin.case@example.com"
                         }))

    def test_missing_name(self):
        self.assertEqual("unknown <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "email": "justin.case@example.com"
                         }))
        self.assertEqual("gerrit <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "email": "justin.case@example.com"
                         }, "gerrit"))
        self.assertEqual("justincase <justin.case@example.com>",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase",
                             "email": "justin.case@example.com"
                         }, "gerrit"))

    def test_missing_email(self):
        self.assertEqual("Justin Case",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase",
                             "name": "Justin Case"
                         }))
        self.assertEqual("Justin Case",
                         gerritchangesource._gerrit_user_to_author({
                             "name": "Justin Case"
                         }))
        self.assertEqual("justincase",
                         gerritchangesource._gerrit_user_to_author({
                             "username": "justincase"
                         }))
        self.assertEqual("unknown",
                         gerritchangesource._gerrit_user_to_author({
                         }))
        self.assertEqual("gerrit",
                         gerritchangesource._gerrit_user_to_author({
                         }, "gerrit"))


class TestGerritChangeSource(changesource.ChangeSourceMixin,
                             TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
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
    expected_change = {'category': 'patchset-created',
                       'files': ['unknown'],
                       'repository': 'ssh://someuser@somehost:29418/pr',
                       'author': 'Dustin <dustin@mozilla.com>',
                       'committer': None,
                       'comments': 'fix 1234',
                       'project': 'pr',
                       'branch': 'br/4321',
                       'revlink': 'http://buildbot.net',
                       'codebase': None,
                       'revision': 'abcdef',
                       'src': None,
                       'when_timestamp': None,
                       'properties': {'event.change.owner.email': 'dustin@mozilla.com',
                                      'event.change.subject': 'fix 1234',
                                      'event.change.project': 'pr',
                                      'event.change.owner.name': 'Dustin',
                                      'event.change.number': '4321',
                                      'event.change.url': 'http://buildbot.net',
                                      'event.change.branch': 'br',
                                      'event.type': 'patchset-created',
                                      'event.patchSet.revision': 'abcdef',
                                      'event.patchSet.number': '12',
                                      'event.source': 'GerritChangeSource'}}

    @defer.inlineCallbacks
    def test_lineReceived_patchset_created(self):
        s = self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps(dict(
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

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        c = self.master.data.updates.changesAdded[0]
        for k, v in c.items():
            self.assertEqual(self.expected_change[k], v)

    @defer.inlineCallbacks
    def test_duplicate_events_ignored(self):
        s = self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps(dict(
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
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

        yield s.lineReceived(json.dumps(dict(
            type="patchset-created",
            change=dict(
                branch="br",
                # Note that this time "project" is a dictionary
                project=dict(name="pr"),
                number="4321",
                owner=dict(name="Dustin", email="dustin@mozilla.com"),
                url="http://buildbot.net",
                subject="fix 1234"
            ),
            patchSet=dict(revision="abcdef", number="12")
        )))
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

    @defer.inlineCallbacks
    def test_malformed_events_ignored(self):
        s = self.newChangeSource('somehost', 'someuser')
        # "change" not in event
        yield s.lineReceived(json.dumps(dict(
            type="patchset-created",
            patchSet=dict(revision="abcdef", number="12")
        )))
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

        # "patchSet" not in event
        yield s.lineReceived(json.dumps(dict(
            type="patchset-created",
            change=dict(
                branch="br",
                # Note that this time "project" is a dictionary
                project=dict(name="pr"),
                number="4321",
                owner=dict(name="Dustin", email="dustin@mozilla.com"),
                url="http://buildbot.net",
                subject="fix 1234"
            ),
        )))
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

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

    @defer.inlineCallbacks
    def test_handled_events_filter_true(self):
        s = self.newChangeSource(
            'somehost', 'some_choosy_user', handled_events=["change-merged"])
        yield s.lineReceived(json.dumps(self.change_merged_event))

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        c = self.master.data.updates.changesAdded[0]
        self.assertEqual(c["category"], "change-merged")
        self.assertEqual(c["branch"], "br")

    @defer.inlineCallbacks
    def test_handled_events_filter_false(self):
        s = self.newChangeSource('somehost', 'some_choosy_user')
        yield s.lineReceived(json.dumps(self.change_merged_event))
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_custom_handler(self):
        s = self.newChangeSource(
            'somehost', 'some_choosy_user',
            handled_events=["change-merged"])

        def custom_handler(self, properties, event):
            event['change']['project'] = "world"
            return self.addChangeFromEvent(properties, event)
        # Patches class to not bother with the inheritance
        s.eventReceived_change_merged = types.MethodType(custom_handler, s)
        yield s.lineReceived(json.dumps(self.change_merged_event))

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        c = self.master.data.updates.changesAdded[0]
        self.assertEqual(c['project'], "world")

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

    # -------------------------------------------------------------------------
    # Test data for getFiles()
    # -------------------------------------------------------------------------
    query_files_success_line1 = {
        "patchSets": [
            {
                "number": 1,
                "files": [
                    {"file": "/COMMIT_MSG", "type": "ADDED", "insertions": 13, "deletions": 0},
                ],
            },
            {
                "number": 13,
                "files": [
                    {"file": "/COMMIT_MSG", "type": "ADDED", "insertions": 13, "deletions": 0},
                    {"file": "file1", "type": "MODIFIED", "insertions": 7, "deletions": 0},
                    {"file": "file2", "type": "MODIFIED", "insertions": 2, "deletions": -2},
                ],
            }
        ]
    }

    query_files_success_line2 = {
        "type": "stats", "rowCount": 1
    }

    query_files_success = '\n'.join([
        json.dumps(query_files_success_line1),
        json.dumps(query_files_success_line2)
    ]).encode('utf8')

    query_files_failure = b'{"type":"stats","rowCount":0}'

    @defer.inlineCallbacks
    def test_getFiles(self):
        s = self.newChangeSource('host', 'user', gerritport=2222)
        exp_argv = [
            'ssh', 'user@host', '-p', '2222', 'gerrit', 'query', '1000',
            '--format', 'JSON', '--files', '--patch-sets'
        ]

        def getoutput_success(cmd, argv, env):
            self.assertEqual([cmd, argv], [exp_argv[0], exp_argv[1:]])
            return self.query_files_success

        def getoutput_failure(cmd, argv, env):
            return self.query_files_failure

        self.patch(utils, 'getProcessOutput', getoutput_success)
        res = yield s.getFiles(1000, 13)
        self.assertEqual(set(res), {'/COMMIT_MSG', 'file1', 'file2'})

        self.patch(utils, 'getProcessOutput', getoutput_failure)
        res = yield s.getFiles(1000, 13)
        self.assertEqual(res, ['unknown'])

    @defer.inlineCallbacks
    def test_getFilesFromEvent(self):
        s = self.newChangeSource('host', 'user', get_files=True,
                                 handled_events=["change-merged"])

        def getoutput(cmd, argv, env):
            return self.query_files_success
        self.patch(utils, 'getProcessOutput', getoutput)

        yield s.lineReceived(json.dumps(self.change_merged_event))
        c = self.master.data.updates.changesAdded[0]
        self.assertEqual(set(c['files']), {'/COMMIT_MSG', 'file1', 'file2'})


class TestGerritEventLogPoller(changesource.ChangeSourceMixin,
                               TestReactorMixin,
                               unittest.TestCase):
    NOW_TIMESTAMP = 1479302598
    EVENT_TIMESTAMP = 1479302599
    NOW_FORMATTED = '2016-11-16 13:23:18'
    EVENT_FORMATTED = '2016-11-16 13:23:19'
    OBJECTID = 1234

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
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
        self.assertSubstring('GerritEventLogPoller',
                             self.changesource.describe())

    @defer.inlineCallbacks
    def test_name(self):
        yield self.newChangeSource()
        self.assertEqual('GerritEventLogPoller:gerrit', self.changesource.name)

    @defer.inlineCallbacks
    def test_lineReceived_patchset_created(self):
        self.master.db.insertTestData([
            fakedb.Object(id=self.OBJECTID, name='GerritEventLogPoller:gerrit',
                          class_name='GerritEventLogPoller')])
        yield self.newChangeSource(get_files=True)
        self.changesource.now = lambda: datetime.datetime.utcfromtimestamp(
            self.NOW_TIMESTAMP)
        thirty_days_ago = (
            datetime.datetime.utcfromtimestamp(self.NOW_TIMESTAMP)
            - datetime.timedelta(days=30))
        self._http.expect(method='get', ep='/plugins/events-log/events/',
                          params={'t1':
                              thirty_days_ago.strftime("%Y-%m-%d %H:%M:%S")},
                          content_json=dict(
                              type="patchset-created",
                              change=dict(
                                  branch="br",
                                  project="pr",
                                  number="4321",
                                  owner=dict(name="Dustin",
                                             email="dustin@mozilla.com"),
                                  url="http://buildbot.net",
                                  subject="fix 1234"
                              ),
                              eventCreatedOn=self.EVENT_TIMESTAMP,
                              patchSet=dict(revision="abcdef", number="12")))

        self._http.expect(
            method='get',
            ep='/changes/4321/revisions/12/files/',
            content=self.change_revision_resp,
        )

        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

        c = self.master.data.updates.changesAdded[0]
        expected_change = dict(TestGerritChangeSource.expected_change)
        expected_change['properties'] = dict(expected_change['properties'])
        expected_change['properties']['event.source'] = 'GerritEventLogPoller'
        for k, v in c.items():
            if k == 'files':
                continue
            self.assertEqual(expected_change[k], v)
        self.master.db.state.assertState(
            self.OBJECTID, last_event_ts=self.EVENT_TIMESTAMP)

        self.assertEqual(set(c['files']), {'/COMMIT_MSG', 'file1'})

        # do a second poll, it should ask for the next events
        self._http.expect(method='get', ep='/plugins/events-log/events/',
                          params={'t1': self.EVENT_FORMATTED},
                          content_json=dict(
                              type="patchset-created",
                              change=dict(
                                  branch="br",
                                  project="pr",
                                  number="4321",
                                  owner=dict(name="Dustin",
                                             email="dustin@mozilla.com"),
                                  url="http://buildbot.net",
                                  subject="fix 1234"
                              ),
                              eventCreatedOn=self.EVENT_TIMESTAMP + 1,
                              patchSet=dict(revision="abcdef", number="12")))

        self._http.expect(
            method='get',
            ep='/changes/4321/revisions/12/files/',
            content=self.change_revision_resp,
        )

        yield self.changesource.poll()
        self.master.db.state.assertState(
            self.OBJECTID, last_event_ts=self.EVENT_TIMESTAMP + 1)

    change_revision_dict = {
        '/COMMIT_MSG': {'status': 'A', 'lines_inserted': 9, 'size_delta': 1, 'size': 1},
        'file1': {'lines_inserted': 9, 'lines_deleted': 2, 'size_delta': 1, 'size': 1},
    }
    change_revision_resp = b')]}\n' + json.dumps(change_revision_dict).encode('utf8')

    @defer.inlineCallbacks
    def test_getFiles(self):
        yield self.newChangeSource(get_files=True)
        yield self.startChangeSource()

        self._http.expect(
            method='get',
            ep='/changes/100/revisions/1/files/',
            content=self.change_revision_resp,
        )

        files = yield self.changesource.getFiles(100, 1)
        self.assertEqual(set(files), {'/COMMIT_MSG', 'file1'})


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
