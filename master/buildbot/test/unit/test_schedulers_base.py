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
from __future__ import division
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot import config
from buildbot.changes import changes
from buildbot.process import properties
from buildbot.schedulers import base
from buildbot.test.fake import fakedb
from buildbot.test.util import scheduler


class BaseScheduler(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 19
    SCHEDULERID = 9
    exp_bsid_brids = (123, {'b': 456})

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, name='testsched', builderNames=['a', 'b'],
                      properties={}, codebases={'': {}}):
        dbBuilder = list()
        builderid = 0
        for builderName in builderNames:
            builderid += 1
            dbBuilder.append(fakedb.Builder(id=builderid, name=builderName))

        self.master.db.insertTestData(dbBuilder)

        sched = self.attachScheduler(
            base.BaseScheduler(name=name, builderNames=builderNames,
                               properties=properties, codebases=codebases),
            self.OBJECTID, self.SCHEDULERID)
        self.master.data.updates.addBuildset = mock.Mock(
            name='data.addBuildset',
            side_effect=lambda *args, **kwargs:
            defer.succeed(self.exp_bsid_brids))

        return sched

    # tests

    def test_constructor_builderNames(self):
        self.assertRaises(config.ConfigErrors,
                          lambda: self.makeScheduler(builderNames='xxx'))

    def test_constructor_builderNames_unicode(self):
        self.makeScheduler(builderNames=[u'a'])

    def test_constructor_codebases_valid(self):
        codebases = {"codebase1":
                     {"repository": u"", "branch": u"", "revision": u""}}
        self.makeScheduler(codebases=codebases)

    def test_constructor_codebases_valid_list(self):
        codebases = ['codebase1']
        self.makeScheduler(codebases=codebases)

    def test_constructor_codebases_invalid(self):
        # scheduler only accepts codebases with at least repository set
        codebases = {"codebase1": {"dictionary": "", "that": "", "fails": ""}}
        self.assertRaises(config.ConfigErrors,
                          lambda: self.makeScheduler(codebases=codebases))

    @defer.inlineCallbacks
    def test_getCodebaseDict(self):
        sched = self.makeScheduler(
            codebases={'lib': {'repository': 'librepo'}})
        cbd = yield sched.getCodebaseDict('lib')
        self.assertEqual(cbd, {'repository': 'librepo'})

    @defer.inlineCallbacks
    def test_getCodebaseDict_constructedFromList(self):
        sched = self.makeScheduler(codebases=['lib', 'lib2'])
        cbd = yield sched.getCodebaseDict('lib')
        self.assertEqual(cbd, {})

    def test_getCodebaseDict_not_found(self):
        sched = self.makeScheduler(
            codebases={'lib': {'repository': 'librepo'}})
        return self.assertFailure(sched.getCodebaseDict('app'), KeyError)

    def test_listBuilderNames(self):
        sched = self.makeScheduler(builderNames=['x', 'y'])
        self.assertEqual(sched.listBuilderNames(), ['x', 'y'])

    @defer.inlineCallbacks
    def test_startConsumingChanges_fileIsImportant_check(self):
        sched = self.makeScheduler()
        try:
            yield sched.startConsumingChanges(fileIsImportant="maybe")
        except AssertionError:
            pass
        else:
            self.fail("didn't assert")

    @defer.inlineCallbacks
    def test_enabled_callback(self):
        sched = self.makeScheduler()
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

    def do_test_change_consumption(self, kwargs, expected_result):
        # (expected_result should be True (important), False (unimportant), or
        # None (ignore the change))
        sched = self.makeScheduler()
        sched.startService()
        self.addCleanup(sched.stopService)

        # set up a change message, a changedict, a change, and convince
        # getChange and fromChdict to convert one to the other
        msg = dict(changeid=12934)

        chdict = dict(changeid=12934, is_chdict=True)

        def getChange(changeid):
            assert changeid == 12934
            return defer.succeed(chdict)
        self.db.changes.getChange = getChange

        change = self.makeFakeChange()
        change.number = 12934

        def fromChdict(cls, master, chdict):
            assert chdict['changeid'] == 12934 and chdict['is_chdict']
            return defer.succeed(change)
        self.patch(changes.Change, 'fromChdict', classmethod(fromChdict))

        change_received = [None]

        def gotChange(got_change, got_important):
            # check that we got the expected change object
            self.assertIdentical(got_change, change)
            change_received[0] = got_important
            return defer.succeed(None)
        sched.gotChange = gotChange

        d = sched.startConsumingChanges(**kwargs)

        def test(_):
            # check that it registered callbacks
            self.assertEqual(len(self.mq.qrefs), 2)

            qref = self.mq.qrefs[1]
            self.assertEqual(qref.filter, ('changes', None, 'new'))

            # invoke the callback with the change, and check the result
            qref.callback('change.12934.new', msg)
            self.assertEqual(change_received[0], expected_result)
        d.addCallback(test)
        return d

    def test_change_consumption_defaults(self):
        # all changes are important by default
        return self.do_test_change_consumption(
            dict(),
            True)

    def test_change_consumption_fileIsImportant_True(self):
        return self.do_test_change_consumption(
            dict(fileIsImportant=lambda c: True),
            True)

    def test_change_consumption_fileIsImportant_False(self):
        return self.do_test_change_consumption(
            dict(fileIsImportant=lambda c: False),
            False)

    def test_change_consumption_fileIsImportant_exception(self):
        d = self.do_test_change_consumption(
            dict(fileIsImportant=lambda c: 1 / 0),
            None)

        def check_err(_):
            self.assertEqual(1, len(self.flushLoggedErrors(ZeroDivisionError)))
        d.addCallback(check_err)
        return d

    def test_change_consumption_change_filter_True(self):
        cf = mock.Mock()
        cf.filter_change = lambda c: True
        return self.do_test_change_consumption(
            dict(change_filter=cf),
            True)

    def test_change_consumption_change_filter_False(self):
        cf = mock.Mock()
        cf.filter_change = lambda c: False
        return self.do_test_change_consumption(
            dict(change_filter=cf),
            None)

    def test_change_consumption_fileIsImportant_False_onlyImportant(self):
        return self.do_test_change_consumption(
            dict(fileIsImportant=lambda c: False, onlyImportant=True),
            None)

    def test_change_consumption_fileIsImportant_True_onlyImportant(self):
        return self.do_test_change_consumption(
            dict(fileIsImportant=lambda c: True, onlyImportant=True),
            True)

    @defer.inlineCallbacks
    def test_activation(self):
        sched = self.makeScheduler(name='n', builderNames=['a'])
        sched.clock = task.Clock()
        sched.activate = mock.Mock(return_value=defer.succeed(None))
        sched.deactivate = mock.Mock(return_value=defer.succeed(None))

        # set the schedulerid, and claim the scheduler on another master
        yield self.setSchedulerToMaster(self.OTHER_MASTER_ID)

        yield sched.startService()
        sched.clock.advance(sched.POLL_INTERVAL_SEC / 2)
        sched.clock.advance(sched.POLL_INTERVAL_SEC / 5)
        sched.clock.advance(sched.POLL_INTERVAL_SEC / 5)
        self.assertFalse(sched.activate.called)
        self.assertFalse(sched.deactivate.called)
        self.assertFalse(sched.isActive())
        # objectid is attached by the test helper
        self.assertEqual(sched.serviceid, self.SCHEDULERID)

        # clear that masterid
        yield sched.stopService()
        self.setSchedulerToMaster(None)
        yield sched.startService()
        sched.clock.advance(sched.POLL_INTERVAL_SEC)
        self.assertTrue(sched.activate.called)
        self.assertFalse(sched.deactivate.called)
        self.assertTrue(sched.isActive())

        # stop the service and see that deactivate is called
        yield sched.stopService()
        self.assertTrue(sched.activate.called)
        self.assertTrue(sched.deactivate.called)
        self.assertFalse(sched.isActive())

    def test_activation_claim_raises(self):
        sched = self.makeScheduler(name='n', builderNames=['a'])
        sched.clock = task.Clock()

        # set the schedulerid, and claim the scheduler on another master
        self.setSchedulerToMaster(RuntimeError())

        sched.startService()
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))
        self.assertFalse(sched.isActive())

    def test_activation_activate_fails(self):
        sched = self.makeScheduler(name='n', builderNames=['a'])
        sched.clock = task.Clock()

        def activate():
            raise RuntimeError('oh noes')
        sched.activate = activate

        sched.startService()
        self.assertEqual(1, len(self.flushLoggedErrors(RuntimeError)))

    @defer.inlineCallbacks
    def do_addBuildsetForSourceStampsWithDefaults(self, codebases,
                                                  sourcestamps,
                                                  exp_sourcestamps):
        sched = self.makeScheduler(name='n', builderNames=['b'],
                                   codebases=codebases)
        bsid, brids = yield sched.addBuildsetForSourceStampsWithDefaults(
            reason=u'power', sourcestamps=sourcestamps, waited_for=False)
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        call = self.master.data.updates.addBuildset.mock_calls[0]

        def sourceStampKey(sourceStamp):
            repository = sourceStamp.get('repository', '')
            if repository is None:
                repository = ''
            branch = sourceStamp.get('branch', '') if not None else ''
            if branch is None:
                branch = ''
            return (repository, branch)

        self.assertEqual(sorted(call[2]['sourcestamps'], key=sourceStampKey),
                         sorted(exp_sourcestamps, key=sourceStampKey))

    def test_addBuildsetForSourceStampsWithDefaults(self):
        codebases = {
            'cbA': dict(repository='svn://A..', branch='stable',
                        revision='13579'),
            'cbB': dict(repository='svn://B..', branch='stable',
                        revision='24680')
        }
        sourcestamps = [
            {'codebase': 'cbA', 'branch': 'AA'},
            {'codebase': 'cbB', 'revision': 'BB'},
        ]
        exp_sourcestamps = [
            {'repository': 'svn://B..', 'branch': 'stable',
             'revision': 'BB', 'codebase': 'cbB', 'project': ''},
            {'repository': 'svn://A..', 'branch': 'AA', 'project': '',
             'revision': '13579', 'codebase': 'cbA'},
        ]
        return self.do_addBuildsetForSourceStampsWithDefaults(
            codebases, sourcestamps, exp_sourcestamps)

    def test_addBuildsetForSourceStampsWithDefaults_fill_in_codebases(self):
        codebases = {
            'cbA': dict(repository='svn://A..', branch='stable',
                        revision='13579'),
            'cbB': dict(repository='svn://B..', branch='stable',
                        revision='24680')
        }
        sourcestamps = [
            {'codebase': 'cbA', 'branch': 'AA'},
        ]
        exp_sourcestamps = [
            {'repository': 'svn://B..', 'branch': 'stable',
             'revision': '24680', 'codebase': 'cbB', 'project': ''},
            {'repository': 'svn://A..', 'branch': 'AA', 'project': '',
             'revision': '13579', 'codebase': 'cbA'},
        ]
        return self.do_addBuildsetForSourceStampsWithDefaults(
            codebases, sourcestamps, exp_sourcestamps)

    def test_addBuildsetForSourceStampsWithDefaults_no_repository(self):
        exp_sourcestamps = [
            {'repository': '', 'branch': None,
             'revision': None, 'codebase': '', 'project': ''},
        ]
        return self.do_addBuildsetForSourceStampsWithDefaults(
            {'': {}}, [], exp_sourcestamps)

    def test_addBuildsetForSourceStamps_unknown_codbases(self):
        codebases = {}
        sourcestamps = [
            {'codebase': 'cbA', 'branch': 'AA'},
            {'codebase': 'cbB', 'revision': 'BB'},
        ]
        exp_sourcestamps = [
            {'branch': None, 'revision': 'BB', 'codebase': 'cbB',
             'project': '', 'repository': ''},
            {'branch': 'AA', 'revision': None, 'codebase': 'cbA',
             'project': '', 'repository': ''},
        ]
        return self.do_addBuildsetForSourceStampsWithDefaults(
            codebases, sourcestamps, exp_sourcestamps)

    @defer.inlineCallbacks
    def test_addBuildsetForChanges_one_change(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        self.db.insertTestData([
            fakedb.Change(changeid=13, sourcestampid=234),
        ])
        bsid, brids = yield sched.addBuildsetForChanges(reason=u'power',
                                                        waited_for=False, changeids=[13])
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=False,
            builderids=[1],
            external_idstring=None,
            properties={
                u'scheduler': ('n', u'Scheduler'),
            },
            reason=u'power',
            scheduler=u'n',
            sourcestamps=[234])

    @defer.inlineCallbacks
    def test_addBuildsetForChanges_properties(self):
        sched = self.makeScheduler(name='n', builderNames=['c'])
        self.db.insertTestData([
            fakedb.Change(changeid=14, sourcestampid=234),
        ])
        bsid, brids = yield sched.addBuildsetForChanges(reason=u'downstream',
                                                        waited_for=False, changeids=[14])
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=False,
            builderids=[1],
            external_idstring=None,
            properties={
                u'scheduler': ('n', u'Scheduler'),
            },
            reason=u'downstream',
            scheduler=u'n',
            sourcestamps=[234])

    @defer.inlineCallbacks
    def test_addBuildsetForChanges_multiple_changes_same_codebase(self):
        # This is a test for backwards compatibility
        # Changes from different repositories come together in one build
        sched = self.makeScheduler(name='n', builderNames=['b', 'c'],
                                   codebases={'cb': {'repository': 'http://repo'}})
        # No codebaseGenerator means all changes have codebase == ''
        self.db.insertTestData([
            fakedb.Change(changeid=13, codebase='cb', sourcestampid=12),
            fakedb.Change(changeid=14, codebase='cb', sourcestampid=11),
            fakedb.Change(changeid=15, codebase='cb', sourcestampid=10),
        ])

        # note that the changeids are given out of order here; it should still
        # use the most recent
        bsid, brids = yield sched.addBuildsetForChanges(reason=u'power',
                                                        waited_for=False, changeids=[14, 15, 13])
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=False,
            builderids=[1, 2],
            external_idstring=None,
            properties={
                u'scheduler': ('n', u'Scheduler'),
            },
            reason=u'power',
            scheduler=u'n',
            sourcestamps=[10])  # sourcestampid from greatest changeid

    @defer.inlineCallbacks
    def test_addBuildsetForChanges_codebases_set_multiple_codebases(self):
        codebases = {'cbA': dict(repository='svn://A..',
                                 branch='stable',
                                 revision='13579'),
                     'cbB': dict(
                         repository='svn://B..',
                         branch='stable',
                         revision='24680'),
                     'cbC': dict(
                         repository='svn://C..',
                         branch='stable',
                         revision='12345'),
                     'cbD': dict(
                         repository='svn://D..')}
        # Scheduler gets codebases that can be used to create extra sourcestamps
        # for repositories that have no changes
        sched = self.makeScheduler(name='n', builderNames=['b', 'c'],
                                   codebases=codebases)
        self.db.insertTestData([
            fakedb.Change(changeid=12, codebase='cbA', sourcestampid=912),
            fakedb.Change(changeid=13, codebase='cbA', sourcestampid=913),
            fakedb.Change(changeid=14, codebase='cbA', sourcestampid=914),
            fakedb.Change(changeid=15, codebase='cbB', sourcestampid=915),
            fakedb.Change(changeid=16, codebase='cbB', sourcestampid=916),
            fakedb.Change(changeid=17, codebase='cbB', sourcestampid=917),
            # note: no changes for cbC or cbD
        ])

        # note that the changeids are given out of order here; it should still
        # use the most recent for each codebase
        bsid, brids = yield sched.addBuildsetForChanges(reason=u'power',
                                                        waited_for=True, changeids=[14, 12, 17, 16, 13, 15])
        self.assertEqual((bsid, brids), self.exp_bsid_brids)

        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=True,
            builderids=[1, 2],
            external_idstring=None,
            reason=u'power',
            scheduler=u'n',
            properties={
                u'scheduler': ('n', u'Scheduler'),
            },
            sourcestamps=[914,
                          917,
                          dict(branch='stable', repository='svn://C..',
                               codebase='cbC', project='', revision='12345'),
                          dict(branch=None, repository='svn://D..', codebase='cbD',
                               project='', revision=None)
                          ]
        )

    @defer.inlineCallbacks
    def test_addBuildsetForSourceStamp(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        bsid, brids = yield sched.addBuildsetForSourceStamps(reason=u'whynot',
                                                             waited_for=False, sourcestamps=[91, {'sourcestamp': True}])
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=False,
            builderids=[1],
            external_idstring=None,
            reason=u'whynot',
            scheduler=u'n',
            properties={
                'scheduler': ('n', 'Scheduler'),
            },
            sourcestamps=[91, {'sourcestamp': True}])

    @defer.inlineCallbacks
    def test_addBuildsetForSourceStamp_explicit_builderNames(self):
        sched = self.makeScheduler(name='n', builderNames=['b', 'x', 'y'])
        bsid, brids = yield sched.addBuildsetForSourceStamps(reason=u'whynot',
                                                             waited_for=True,
                                                             sourcestamps=[
                                                                 91, {'sourcestamp': True}],
                                                             builderNames=['x', 'y'])
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=True,
            builderids=[2, 3],
            external_idstring=None,
            reason=u'whynot',
            scheduler=u'n',
            properties={
                'scheduler': ('n', 'Scheduler'),
            },
            sourcestamps=[91, {'sourcestamp': True}])

    @defer.inlineCallbacks
    def test_addBuildsetForSourceStamp_properties(self):
        props = properties.Properties(xxx="yyy")
        sched = self.makeScheduler(name='n', builderNames=['b'])
        bsid, brids = yield sched.addBuildsetForSourceStamps(reason=u'whynot',
                                                             waited_for=False,
                                                             sourcestamps=[91], properties=props)
        self.assertEqual((bsid, brids), self.exp_bsid_brids)
        self.master.data.updates.addBuildset.assert_called_with(
            waited_for=False,
            builderids=[1],
            external_idstring=None,
            properties={
                u'xxx': ('yyy', u'TEST'),
                u'scheduler': (u'n', u'Scheduler')},
            reason=u'whynot',
            scheduler=u'n',
            sourcestamps=[91])

    def test_signature_addBuildsetForChanges(self):
        sched = self.makeScheduler(builderNames=['xxx'])

        @self.assertArgSpecMatches(
            sched.addBuildsetForChanges,  # Real
            self.fake_addBuildsetForChanges,  # Real
        )
        def addBuildsetForChanges(self, waited_for=False, reason='',
                                  external_idstring=None, changeids=None, builderNames=None,
                                  properties=None,
                                  **kw):
            pass

    def test_signature_addBuildsetForSourceStamps(self):
        sched = self.makeScheduler(builderNames=['xxx'])

        @self.assertArgSpecMatches(
            sched.addBuildsetForSourceStamps,  # Real
            self.fake_addBuildsetForSourceStamps,  # Fake
        )
        def addBuildsetForSourceStamps(self, waited_for=False, sourcestamps=None,
                                       reason='', external_idstring=None, properties=None,
                                       builderNames=None, **kw):
            pass

    def test_signature_addBuildsetForSourceStampsWithDefaults(self):
        sched = self.makeScheduler(builderNames=['xxx'])

        @self.assertArgSpecMatches(
            sched.addBuildsetForSourceStampsWithDefaults,  # Real
            self.fake_addBuildsetForSourceStampsWithDefaults,  # Fake
        )
        def addBuildsetForSourceStampsWithDefaults(self, reason, sourcestamps=None,
                                                   waited_for=False, properties=None, builderNames=None,
                                                   **kw):
            pass
