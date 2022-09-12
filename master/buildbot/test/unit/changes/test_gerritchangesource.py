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

import copy
import datetime
import json
import types

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

from buildbot.changes import gerritchangesource
from buildbot.test import fakedb
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.change import Change
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.test.util import changesource


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


class TestGerritChangeSource(MasterRunProcessMixin, changesource.ChangeSourceMixin,
                             TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.setup_master_run_process()
        return self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    @defer.inlineCallbacks
    def newChangeSource(self, host, user, *args, **kwargs):
        s = gerritchangesource.GerritChangeSource(
            host, user, *args, **kwargs)
        yield self.attachChangeSource(s)
        s.configureService()
        return s

    def assert_changes(self, expected_changes, ignore_keys):
        self.assertEqual(len(self.master.data.updates.changesAdded), len(expected_changes))
        for i, expected_change in enumerate(expected_changes):
            change = self.master.data.updates.changesAdded[i]
            for key in ignore_keys:
                del change[key]
            self.assertEqual(change, expected_change)

    # tests

    @defer.inlineCallbacks
    def test_describe(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        self.assertSubstring("GerritChangeSource", s.describe())

    @defer.inlineCallbacks
    def test_name(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        self.assertEqual("GerritChangeSource:someuser@somehost:29418", s.name)

        s = yield self.newChangeSource('somehost', 'someuser', name="MyName")
        self.assertEqual("MyName", s.name)

    # TODO: test the backoff algorithm

    patchset_created_event = {
        "uploader": {
            'name': 'uploader uploader',
            'email': 'uploader@example.com',
            'username': 'uploader'
        },
        "patchSet": {
            "number": 1,
            "revision": "29b73c3eb1aeaa9e6c7da520a940d60810e883db",
            "parents": ["7e563631188dcadf32aad0d8647c818834921a1e"],
            "ref": "refs/changes/21/4321/1",
            "uploader": {
                'name': 'uploader uploader',
                'email': 'uploader@example.com',
                'username': 'uploader'
            },
            "createdOn": 1627214047,
            "author": {
                'name': 'author author',
                'email': 'author@example.com',
                'username': 'author'
            },
            "kind": "REWORK",
            "sizeInsertions": 1,
            "sizeDeletions": 0
        },
        "change": {
            "project": "test",
            "branch": "master",
            "id": "I21234123412341234123412341234",
            "number": 4321,
            "subject": "change subject",
            "owner": {
                'name': 'owner owner',
                'email': 'owner@example.com',
                'username': 'owner'
            },
            "url": "http://example.com/c/test/+/4321",
            "commitMessage": "test1\n\nChange-Id: I21234123412341234123412341234\n",
            "createdOn": 1627214047,
            "status": "NEW"
        },
        "project": "test",
        "refName": "refs/heads/master",
        "changeKey": {"id": "I21234123412341234123412341234"},
        "type": "patchset-created",
        "eventCreatedOn": 1627214048
    }

    # this variable is reused in test_steps_source_repo
    # to ensure correct integration between change source and repo step
    expected_change_patchset_created = {
        'category': 'patchset-created',
        'files': ['unknown'],
        'repository': 'ssh://someuser@somehost:29418/test',
        'author': 'owner owner <owner@example.com>',
        'committer': None,
        'comments': 'change subject',
        'project': 'test',
        'branch': 'refs/changes/21/4321/1',
        'revision': '29b73c3eb1aeaa9e6c7da520a940d60810e883db',
        'codebase': None,
        'revlink': 'http://example.com/c/test/+/4321',
        'src': None,
        'when_timestamp': None,
    }

    @defer.inlineCallbacks
    def test_lineReceived_patchset_created(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps(self.patchset_created_event))

        self.assert_changes([self.expected_change_patchset_created], ignore_keys=['properties'])

    @defer.inlineCallbacks
    def test_lineReceived_patchset_created_props(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps(self.patchset_created_event))

        change = copy.deepcopy(self.expected_change_patchset_created)
        change['properties'] = {
            'event.change.branch': 'master',
            'event.change.commitMessage': 'test1\n\nChange-Id: I21234123412341234123412341234\n',
            'event.change.createdOn': 1627214047,
            'event.change.id': 'I21234123412341234123412341234',
            'event.change.number': 4321,
            'event.change.owner.email': 'owner@example.com',
            'event.change.owner.name': 'owner owner',
            'event.change.owner.username': 'owner',
            'event.change.project': 'test',
            'event.change.status': 'NEW',
            'event.change.subject': 'change subject',
            'event.change.url': 'http://example.com/c/test/+/4321',
            'event.changeKey.id': 'I21234123412341234123412341234',
            'event.patchSet.author.email': 'author@example.com',
            'event.patchSet.author.name': 'author author',
            'event.patchSet.author.username': 'author',
            'event.patchSet.createdOn': 1627214047,
            'event.patchSet.kind': 'REWORK',
            'event.patchSet.number': 1,
            'event.patchSet.parents': ['7e563631188dcadf32aad0d8647c818834921a1e'],
            'event.patchSet.ref': 'refs/changes/21/4321/1',
            'event.patchSet.revision': '29b73c3eb1aeaa9e6c7da520a940d60810e883db',
            'event.patchSet.sizeDeletions': 0,
            'event.patchSet.sizeInsertions': 1,
            'event.patchSet.uploader.email': 'uploader@example.com',
            'event.patchSet.uploader.name': 'uploader uploader',
            'event.patchSet.uploader.username': 'uploader',
            'event.project': 'test',
            'event.refName': 'refs/heads/master',
            'event.source': 'GerritChangeSource',
            'event.type': 'patchset-created',
            'event.uploader.email': 'uploader@example.com',
            'event.uploader.name': 'uploader uploader',
            'event.uploader.username': 'uploader',
            'target_branch': 'master',
        }
        self.maxDiff = None
        self.assert_changes([change], ignore_keys=[])

    comment_added_event = {
        "type": "comment-added",
        "author": {
            'name': 'author author',
            'email': 'author@example.com',
            'username': 'author'
        },
        "approvals": [{"type": "Code-Review", "description": "Code-Review", "value": "0"}],
        "comment": "Patch Set 1:\n\ntest comment",
        "patchSet": {
            "number": 1,
            "revision": "29b73c3eb1aeaa9e6c7da520a940d60810e883db",
            "parents": ["7e563631188dcadf32aad0d8647c818834921a1e"],
            "ref": "refs/changes/21/4321/1",
            "uploader": {
                'name': 'uploader uploader',
                'email': 'uploader@example.com',
                'username': 'uploader'
            },
            "createdOn": 1627214047,
            "author": {
                'name': 'author author',
                'email': 'author@example.com',
                'username': 'author'
            },
            "kind": "REWORK",
            "sizeInsertions": 1,
            "sizeDeletions": 0
        },
        "change": {
            "project": "test",
            "branch": "master",
            "id": "I21234123412341234123412341234",
            "number": 4321,
            "subject": "change subject",
            "owner": {
                'name': 'owner owner',
                'email': 'owner@example.com',
                'username': 'owner'
            },
            "url": "http://example.com/c/test/+/4321",
            "commitMessage": "test1\n\nChange-Id: I21234123412341234123412341234\n",
            "createdOn": 1627214047,
            "status": "NEW"
        },
        "project": "test",
        "refName": "refs/heads/master",
        "changeKey": {"id": "I21234123412341234123412341234"},
        "eventCreatedOn": 1627214102
    }

    expected_change_comment_added = {
        'category': 'comment-added',
        'files': ['unknown'],
        'repository': 'ssh://someuser@somehost:29418/test',
        'author': 'owner owner <owner@example.com>',
        'committer': None,
        'comments': 'change subject',
        'project': 'test',
        'branch': 'refs/changes/21/4321/1',
        'revlink': 'http://example.com/c/test/+/4321',
        'codebase': None,
        'revision': '29b73c3eb1aeaa9e6c7da520a940d60810e883db',
        'src': None,
        'when_timestamp': None,
    }

    @defer.inlineCallbacks
    def test_lineReceived_comment_added(self):
        s = yield self.newChangeSource('somehost', 'someuser', handled_events=["comment-added"])
        yield s.lineReceived(json.dumps(self.comment_added_event))

        self.assert_changes([self.expected_change_comment_added], ignore_keys=['properties'])

    @defer.inlineCallbacks
    def test_lineReceived_ref_updated(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps({
            'type': 'ref-updated',
            'submitter': {
                'name': 'tester',
                'email': 'tester@example.com',
                'username': 'tester'
            },
            'refUpdate': {
                'oldRev': '12341234',
                'newRev': '56785678',
                'refName': 'refs/heads/master',
                'project': 'test'
            },
            'eventCreatedOn': 1614528683
        }))
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        c = self.master.data.updates.changesAdded[0]
        self.assertEqual(c, {
            'files': ['unknown'],
            'comments': 'Gerrit: commit(s) pushed.',
            'author': 'tester <tester@example.com>',
            'committer': None,
            'revision': '56785678',
            'when_timestamp': None,
            'branch': 'master',
            'category': 'ref-updated',
            'revlink': '',
            'properties': {
                'event.type': 'ref-updated',
                'event.submitter.name': 'tester',
                'event.submitter.email':
                    'tester@example.com',
                    'event.submitter.username': 'tester',
                    'event.refUpdate.oldRev': '12341234',
                    'event.refUpdate.newRev': '56785678',
                    'event.refUpdate.refName': 'refs/heads/master',
                    'event.refUpdate.project': 'test',
                    'event.source': 'GerritChangeSource'
                },
            'repository': 'ssh://someuser@somehost:29418/test',
            'codebase': None,
            'project': 'test',
            'src': None
        })

    @defer.inlineCallbacks
    def test_lineReceived_ref_updated_for_change(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps({
            'type': 'ref-updated',
            'submitter': {
                'name': 'tester',
                'email': 'tester@example.com',
                'username': 'tester'
            },
            'refUpdate': {
                'oldRev': '00000000',
                'newRev': '56785678',
                'refName': 'refs/changes/12/432112/1',
                'project': 'test'
            },
            'eventCreatedOn': 1614528683
        }))
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_duplicate_events_ignored(self):
        s = yield self.newChangeSource('somehost', 'someuser')
        yield s.lineReceived(json.dumps(self.patchset_created_event))
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

        patchset_created_event = copy.deepcopy(self.patchset_created_event)
        patchset_created_event['change']['project'] = {'name': 'test'}

        yield s.lineReceived(json.dumps(patchset_created_event))
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

    @defer.inlineCallbacks
    def test_duplicate_non_source_events_not_ignored(self):
        s = yield self.newChangeSource('somehost', 'someuser',
                                       handled_events=['patchset-created', 'ref-updated',
                                                       'change-merged', 'comment-added'])
        yield s.lineReceived(json.dumps(self.comment_added_event))
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

        yield s.lineReceived(json.dumps(self.comment_added_event))
        self.assertEqual(len(self.master.data.updates.changesAdded), 2)

    @defer.inlineCallbacks
    def test_malformed_events_ignored(self):
        s = yield self.newChangeSource('somehost', 'someuser')
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
        s = yield self.newChangeSource('somehost', 'some_choosy_user',
                                       handled_events=["change-merged"])
        yield s.lineReceived(json.dumps(self.change_merged_event))

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        c = self.master.data.updates.changesAdded[0]
        self.assertEqual(c["category"], "change-merged")
        self.assertEqual(c["branch"], "br")

    @defer.inlineCallbacks
    def test_handled_events_filter_false(self):
        s = yield self.newChangeSource('somehost', 'some_choosy_user')
        yield s.lineReceived(json.dumps(self.change_merged_event))
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_custom_handler(self):
        s = yield self.newChangeSource('somehost', 'some_choosy_user',
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

    @defer.inlineCallbacks
    def test_startStreamProcess_bytes_output(self):
        s = yield self.newChangeSource('somehost', 'some_choosy_user', debug=True)

        exp_argv = ['ssh', '-o', 'BatchMode=yes', 'some_choosy_user@somehost', '-p', '29418']
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
        s = yield self.newChangeSource('host', 'user', gerritport=2222)
        exp_argv = [
            'ssh', '-o', 'BatchMode=yes', 'user@host', '-p', '2222',
            'gerrit', 'query', '1000', '--format', 'JSON', '--files', '--patch-sets'
        ]

        self.expect_commands(
            ExpectMasterShell(exp_argv)
            .stdout(self.query_files_success),
            ExpectMasterShell(exp_argv)
            .stdout(self.query_files_failure)
        )

        res = yield s.getFiles(1000, 13)
        self.assertEqual(set(res), {'/COMMIT_MSG', 'file1', 'file2'})

        res = yield s.getFiles(1000, 13)
        self.assertEqual(res, ['unknown'])

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_getFilesFromEvent(self):
        self.expect_commands(
            ExpectMasterShell(['ssh', '-o', 'BatchMode=yes', 'user@host', '-p', '29418', 'gerrit',
                          'query', '4321', '--format', 'JSON', '--files', '--patch-sets'])
            .stdout(self.query_files_success)
        )

        s = yield self.newChangeSource('host', 'user', get_files=True,
                                       handled_events=["change-merged"])

        yield s.lineReceived(json.dumps(self.change_merged_event))
        c = self.master.data.updates.changesAdded[0]
        self.assertEqual(set(c['files']), {'/COMMIT_MSG', 'file1', 'file2'})

        self.assert_all_commands_ran()


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
        self.setup_test_reactor()
        yield self.setUpChangeSource()
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        yield self.tearDownChangeSource()

    @defer.inlineCallbacks
    def newChangeSource(self, **kwargs):
        auth = kwargs.pop('auth', ('log', 'pass'))
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'gerrit', auth=auth)
        self.changesource = gerritchangesource.GerritEventLogPoller(
            'gerrit', auth=auth, gitBaseURL="ssh://someuser@somehost:29418", pollAtLaunch=False,
            **kwargs)

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
        # describe is not used yet in buildbot nine, but it can still be useful in the future, so
        # lets implement and test it
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
                                  branch="master",
                                  project="test",
                                  number="4321",
                                  owner=dict(name="owner owner",
                                             email="owner@example.com"),
                                  url="http://example.com/c/test/+/4321",
                                  subject="change subject"
                              ),
                              eventCreatedOn=self.EVENT_TIMESTAMP,
                              patchSet={
                                  'revision': "29b73c3eb1aeaa9e6c7da520a940d60810e883db",
                                  'number': "1",
                                  'ref': 'refs/changes/21/4321/1'}
                              ))

        self._http.expect(
            method='get',
            ep='/changes/4321/revisions/1/files/',
            content=self.change_revision_resp,
        )

        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

        c = self.master.data.updates.changesAdded[0]
        expected_change = dict(TestGerritChangeSource.expected_change_patchset_created)
        for k, v in c.items():
            if k in ('files', 'properties'):
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
                              patchSet={
                                  'revision': "29b73c3eb1aeaa9e6c7da520a940d60810e883db",
                                  'number': "1",
                                  'ref': 'refs/changes/21/4321/1'}
                              ))

        self._http.expect(
            method='get',
            ep='/changes/4321/revisions/1/files/',
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

    def test_event_type(self):
        props = {
            'event.type': 'patchset-created',
            'event.change.branch': 'master',
        }

        ch = Change(**TestGerritChangeSource.expected_change_patchset_created, properties=props)
        f = gerritchangesource.GerritChangeFilter(
            branch=["master"], eventtype=["patchset-created"])
        self.assertTrue(f.filter_change(ch))
        f = gerritchangesource.GerritChangeFilter(
            branch="master2", eventtype=["patchset-created"])
        self.assertFalse(f.filter_change(ch))
        f = gerritchangesource.GerritChangeFilter(
            branch="master", eventtype="ref-updated")
        self.assertFalse(f.filter_change(ch))
        self.assertEqual(
            repr(f),
            '<GerritChangeFilter on event.type in [\'ref-updated\'] and '
            'event.change.branch in [\'master\']>')

    def create_props(self, branch, event_type):
        return {
            'event.type': event_type,
            'event.change.branch': branch,
        }

    def test_event_type_re(self):
        f = gerritchangesource.GerritChangeFilter(eventtype_re="patchset-.*")
        self.assertTrue(f.filter_change(
            Change(properties=self.create_props("br", "patchset-created"))
        ))
        self.assertFalse(f.filter_change(
            Change(properties=self.create_props("br", "ref-updated"))
        ))

    def test_event_type_fn(self):
        f = gerritchangesource.GerritChangeFilter(eventtype_fn=lambda t: t == "patchset-created")
        self.assertTrue(f.filter_change(
            Change(properties=self.create_props("br", "patchset-created"))
        ))
        self.assertFalse(f.filter_change(
            Change(properties=self.create_props("br", "ref-updated"))
        ))
        self.assertEqual(repr(f), '<GerritChangeFilter on <lambda>(eventtype)>')

    def test_branch_fn(self):
        f = gerritchangesource.GerritChangeFilter(branch_fn=lambda t: t == "br0")
        self.assertTrue(f.filter_change(
            Change(properties=self.create_props("br0", "patchset-created"))
        ))
        self.assertFalse(f.filter_change(
            Change(properties=self.create_props("br1", "ref-updated"))
        ))
        self.assertEqual(repr(f), '<GerritChangeFilter on <lambda>(branch)>')
