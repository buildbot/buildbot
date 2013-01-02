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

import sys
import mock
import twisted
from twisted.trial import unittest
from twisted.internet import defer
from buildbot import config
from buildbot.schedulers import base
from buildbot.changes import changes
from buildbot.process import properties
from buildbot.test.util import scheduler
from buildbot.test.fake import fakedb

class BaseScheduler(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 19

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, name='testsched', builderNames=['a', 'b'],
                            properties={}, codebases = {'':{}}):
        sched = self.attachScheduler(
                base.BaseScheduler(name=name, builderNames=builderNames,
                                   properties=properties, codebases=codebases),
                self.OBJECTID)

        return sched

    def checkBuildsetAdded(self, res, builderNames=[], external_idstring=u'',
            properties={}, reason=u'', scheduler=u'', sourcestamps=[]):
        """A callback for addBuildsetForXxx, checking that the results are as
        expected.  The parameters give the expected values.
        """
        got_bsid, got_brids = res
        bs = self.master.data.updates.buildsetsAdded[0]

        got, exp = {}, {}
        got['numBuildrequests'] = len(got_brids)
        exp['numBuildrequests'] = len(builderNames)
        got['bsid'] = got_bsid
        exp['bsid'] = 200 + len(self.master.data.updates.buildsetsAdded) - 1
        got['builderNames'] = sorted(bs['builderNames'])
        exp['builderNames'] = sorted(builderNames)
        got['external_idstring'] = bs['external_idstring']
        exp['external_idstring'] = external_idstring
        got['properties'] = bs['properties']
        exp['properties'] = properties.copy()
        exp['properties']['scheduler'] = (scheduler, u'Scheduler')
        got['reason'] = bs['reason']
        exp['reason'] = reason
        got['scheduler'] = bs['scheduler']
        exp['scheduler'] = scheduler

        # TODO: refactor once sourcestamps are in the data API
        self.master.db.sourcestamps.assertSourceStamps(
                bs['sourcestampsetid'], sourcestamps)

        self.assertEqual(got, exp)

    # tests

    def test_constructor_builderNames(self):
        self.assertRaises(config.ConfigErrors,
                lambda : self.makeScheduler(builderNames='xxx'))

    def test_constructor_builderNames_unicode(self):
        self.makeScheduler(builderNames=[u'a'])

    def test_constructor_codebases_valid(self):
        codebases = {"codebase1":
                    {"repository":u"", "branch":u"", "revision":u""}}
        self.makeScheduler(codebases = codebases)

    def test_constructor_codebases_invalid(self):
        # scheduler only accepts codebases with at least repository set
        codebases = {"codebase1": {"dictionary":"", "that":"", "fails":""}}
        self.assertRaises(config.ConfigErrors,
                            lambda : self.makeScheduler(codebases = codebases))

    def test_listBuilderNames(self):
        sched = self.makeScheduler(builderNames=['x', 'y'])
        self.assertEqual(sched.listBuilderNames(), ['x', 'y'])

    def test_getPendingBuildTimes(self):
        sched = self.makeScheduler()
        self.assertEqual(sched.getPendingBuildTimes(), [])

    def test_addBuildsetForLatest_defaults(self):
        sched = self.makeScheduler(name='testy', builderNames=['x'],
                                        properties=dict(a='b'))
        d = sched.addBuildsetForLatest(reason=u'because')
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['x'],
                external_idstring=None,
                properties={ u'a': ('b', u'Scheduler') },
                reason=u'because',
                scheduler=u'testy',
                sourcestamps=[
                    dict(branch=None, revision=None, repository='',
                            codebase='', project=''),
                ])
        return d

    def test_startConsumingChanges_fileIsImportant_check(self):
        sched = self.makeScheduler()
        self.assertRaises(AssertionError,
                lambda : sched.startConsumingChanges(fileIsImportant="maybe"))

    def do_test_change_consumption(self, kwargs, expected_result):
        # (expected_result should be True (important), False (unimportant), or
        # None (ignore the change))
        sched = self.makeScheduler()
        sched.startService()

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

        change_received = [ None ]
        def gotChange(got_change, got_important):
            # check that we got the expected change object
            self.assertIdentical(got_change, change)
            change_received[0] = got_important
            return defer.succeed(None)
        sched.gotChange = gotChange

        d = sched.startConsumingChanges(**kwargs)
        def test(_):
            # check that it registered a callback
            self.assertEqual(len(self.mq.qrefs), 1)
            qref = self.mq.qrefs[0]
            self.assertEqual(qref.filter, ('change', None, 'new'))

            # invoke the callback with the change, and check the result
            qref.callback('change.12934.new', msg)
            self.assertEqual(change_received[0], expected_result)
        d.addCallback(test)
        d.addCallback(lambda _ : sched.stopService())
        return d

    def test_change_consumption_defaults(self):
        # all changes are important by default
        return self.do_test_change_consumption(
                dict(),
                True)

    def test_change_consumption_fileIsImportant_True(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : True),
                True)

    def test_change_consumption_fileIsImportant_False(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : False),
                False)

    def test_change_consumption_fileIsImportant_exception(self):
        d = self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : 1/0),
                None)
        def check_err(_):
            self.assertEqual(1, len(self.flushLoggedErrors(ZeroDivisionError)))
        d.addCallback(check_err)
        return d
    if twisted.version.major <= 9 and sys.version_info[:2] >= (2,7):
        test_change_consumption_fileIsImportant_exception.skip = \
            "flushLoggedErrors does not work correctly on 9.0.0 and earlier with Python-2.7"

    def test_change_consumption_change_filter_True(self):
        cf = mock.Mock()
        cf.filter_change = lambda c : True
        return self.do_test_change_consumption(
                dict(change_filter=cf),
                True)

    def test_change_consumption_change_filter_False(self):
        cf = mock.Mock()
        cf.filter_change = lambda c : False
        return self.do_test_change_consumption(
                dict(change_filter=cf),
                None)

    def test_change_consumption_fileIsImportant_False_onlyImportant(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : False, onlyImportant=True),
                None)

    def test_change_consumption_fileIsImportant_True_onlyImportant(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : True, onlyImportant=True),
                True)

    def test_addBuilsetForLatest_args(self):
        sched = self.makeScheduler(name='xyz', builderNames=['y', 'z'])
        d = sched.addBuildsetForLatest(reason=u'cuz', branch='default',
                    project='myp', repository='hgmo',
                    external_idstring=u'try_1234')
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['y', 'z'],
                external_idstring=u'try_1234',
                reason=u'cuz',
                scheduler=u'xyz',
                sourcestamps=[
                    dict(branch='default', revision=None, repository='hgmo',
                            codebase='', project='myp'),
                ])
        return d

    def test_addBuildsetForLatest_properties(self):
        props = properties.Properties(xxx="yyy")
        sched = self.makeScheduler(name='xyz', builderNames=['y', 'z'])
        d = sched.addBuildsetForLatest(reason=u'cuz', branch=u'default',
                    project=u'myp', repository=u'hgmo',
                    external_idstring=u'try_1234', properties=props)
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['y', 'z'],
                external_idstring=u'try_1234',
                properties = { u'xxx' : ( 'yyy', u'TEST') },
                reason=u'cuz',
                scheduler=u'xyz',
                sourcestamps=[
                    dict(branch='default', revision=None, repository='hgmo',
                            codebase='', project='myp'),
                ])
        return d

    def test_addBuildsetForLatest_builderNames(self):
        sched = self.makeScheduler(name='xyz', builderNames=['y', 'z'])
        d = sched.addBuildsetForLatest(reason=u'cuz', branch=u'default',
                    builderNames=['y', 'z'])
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['y', 'z'],
                external_idstring=None,
                reason=u'cuz',
                scheduler=u'xyz',
                sourcestamps=[
                    dict(branch='default', revision=None, repository='',
                        codebase='', project=''),
                ])
        return d

    def test_addBuildsetForChanges_one_change(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                            repository='svn://...', codebase='',
                            project='world-domination'),
        ])
        d = sched.addBuildsetForChanges(reason=u'power', changeids=[13])
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['b'],
                external_idstring=None,
                reason=u'power',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='trunk', repository='svn://...', codebase='',
                        changeids=set([13]), project='world-domination',
                        revision='9283'),
                ])
        return d

    def test_addBuildsetForChanges_properties(self):
        props = properties.Properties(xxx="yyy")
        sched = self.makeScheduler(name='n', builderNames=['c'])
        self.db.insertTestData([
            fakedb.Change(changeid=14, branch='default', revision='123:abc',
                            repository='', project='', codebase=''),
        ])
        d = sched.addBuildsetForChanges(reason=u'downstream', changeids=[14],
                            properties=props)
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['c'],
                external_idstring=None,
                properties={ u'xxx' : ( 'yyy', u'TEST') },
                reason=u'downstream',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='default', revision='123:abc', repository='',
                        project='', changeids=set([14]), codebase=''),
                ])
        return d

    def test_addBuildsetForChanges_one_change_builderNames(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                          codebase='', repository='svn://...', 
                          project='world-domination'),
        ])
        d = sched.addBuildsetForChanges(reason=u'power', changeids=[13],
                            builderNames=['p'])
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['p'],
                external_idstring=None,
                reason=u'power',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='trunk', repository='svn://...', codebase='',
                        changeids=set([13]), project='world-domination',
                        revision='9283'),
                ])
        return d

    def test_addBuildsetForChanges_multiple_changes_no_codebaseGenerator(self):
        # This is a test for backwards compatibility
        # Changes from different repositories come together in one build
        sched = self.makeScheduler(name='n', builderNames=['b', 'c'])
        # No codebaseGenerator means all changes have codebase == ''
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                            repository='svn://A..', project='knitting',
                            codebase=''),
            fakedb.Change(changeid=14, branch='devel', revision='9284',
                            repository='svn://B..', project='making-tea',
                            codebase=''),
            fakedb.Change(changeid=15, branch='trunk', revision='9285',
                            repository='svn://C..', project='world-domination',
                            codebase=''),
        ])

        # note that the changeids are given out of order here; it should still
        # use the most recent
        d = sched.addBuildsetForChanges(reason=u'power', changeids=[14, 15, 13])
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['b', 'c'],
                external_idstring=None,
                reason=u'power',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='trunk', repository='svn://C..', codebase='',
                        changeids=set([13,14,15]), project='world-domination',
                        revision='9285'),
                ])
        return d

    def test_addBuildsetForChanges_multiple_changes_single_codebase(self):
        sched = self.makeScheduler(name='n', builderNames=['b', 'c'])
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                            repository='svn://...', project='knitting',
                            codebase=''),
            fakedb.Change(changeid=14, branch='devel', revision='9284',
                            repository='svn://...', project='making-tea',
                            codebase=''),
            fakedb.Change(changeid=15, branch='trunk', revision='9285',
                            repository='svn://...', project='world-domination',
                            codebase=''),
        ])

        # note that the changeids are given out of order here; it should still
        # use the most recent
        d = sched.addBuildsetForChanges(reason=u'power', changeids=[14, 15, 13])
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['b', 'c'],
                external_idstring=None,
                reason=u'power',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='trunk', repository='svn://...', codebase='',
                        changeids=set([13,14,15]), project='world-domination',
                        revision='9285'),
                ])
        return d

    def test_addBuildsetForChanges_codebases_set_multiple_changed_codebases(self):
        codebases = { 'cbA':dict(
                            repository='svn://A..', 
                            branch='stable', 
                            revision='13579'),
                      'cbB':dict(
                            repository='svn://B..', 
                            branch='stable', 
                            revision='24680'),
                      'cbC':dict(
                            repository='svn://C..', 
                            branch='stable', 
                            revision='12345'),
                      'cbD':dict(
                            repository='svn://D..')}
        # Scheduler gets codebases that can be used to create extra sourcestamps
        # for repositories that have no changes
        sched = self.makeScheduler(name='n', builderNames=['b', 'c'], 
                                   codebases=codebases)
        self.db.insertTestData([
            fakedb.Change(changeid=12, branch='trunk', revision='9282',
                            repository='svn://A..', project='playing',
                            codebase='cbA'),
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                            repository='svn://A..', project='knitting',
                            codebase='cbA'),
            fakedb.Change(changeid=14, branch='develop', revision='9284',
                            repository='svn://A..', project='making-tea',
                            codebase='cbA'),
            fakedb.Change(changeid=15, branch='trunk', revision='8085',
                            repository='svn://B..', project='boxing',
                            codebase='cbB'),
            fakedb.Change(changeid=16, branch='develop', revision='8086',
                            repository='svn://B..', project='playing soccer',
                            codebase='cbB'),
            fakedb.Change(changeid=17, branch='develop', revision='8087',
                            repository='svn://B..', project='swimming',
                            codebase='cbB'),
        ])

        # note that the changeids are given out of order here; it should still
        # use the most recent for each codebase
        d = sched.addBuildsetForChanges(reason=u'power',
                changeids=[14, 12, 17, 16, 13, 15])
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['b', 'c'],
                external_idstring=None,
                reason=u'power',
                scheduler=u'n',
                sourcestamps=[
                     dict(branch='develop', repository='svn://A..',
                         codebase='cbA', changeids=set([12,13,14]),
                         project='making-tea', revision='9284'),
                     dict(branch='develop', repository='svn://B..',
                         codebase='cbB', changeids=set([15,16,17]),
                         project='swimming', revision='8087'),
                     dict(branch='stable', repository='svn://C..',
                         codebase='cbC', project='', revision='12345'),
                     dict(branch=None, repository='svn://D..', codebase='cbD',
                         project='', revision=None),
                ])
        return d

    def test_addBuildsetForSourceStamp(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        d = self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, branch='fixins',
                revision='abc', patchid=None, repository='r',
                project='p'),
        ])
        d.addCallback(lambda _ :
                sched.addBuildsetForSourceStamp(reason=u'whynot', setid=1091))
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['b'],
                external_idstring=None,
                reason=u'whynot',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='fixins', revision='abc', repository='r',
                        project='p', codebase=''),
                ])
        return d

    def test_addBuildsetForSourceStamp_properties(self):
        props = properties.Properties(xxx="yyy")
        sched = self.makeScheduler(name='n', builderNames=['b'])
        d = self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, branch='fixins',
                revision='abc', patchid=None, repository='r', codebase='cb',
                project='p'),
        ])
        d.addCallback(lambda _ :
            sched.addBuildsetForSourceStamp(reason=u'whynot', setid=1091,
                                            properties=props))
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['b'],
                external_idstring=None,
                properties={ u'xxx' : ( 'yyy', u'TEST' ) },
                reason=u'whynot',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='fixins', revision='abc', repository='r',
                        codebase='cb', project='p'),
                ])
        return d

    def test_addBuildsetForSourceStamp_builderNames(self):
        sched = self.makeScheduler(name='n', builderNames=['k'])
        d = self.db.insertTestData([
            fakedb.SourceStampSet(id=1091),
            fakedb.SourceStamp(id=91, sourcestampsetid=1091, branch='fixins',
                revision='abc', patchid=None, repository='r', codebase='cb',
                project='p'),
        ])
        d.addCallback(lambda _ :
            sched.addBuildsetForSourceStamp(reason=u'whynot', setid = 1091,
                        builderNames=['a', 'b']))
        d.addCallback(self.checkBuildsetAdded,
                builderNames=['a', 'b'],
                external_idstring=None,
                reason=u'whynot',
                scheduler=u'n',
                sourcestamps=[
                    dict(branch='fixins', revision='abc', repository='r',
                        codebase='cb', project='p'),
                ])
        return d

    def test_findNewSchedulerInstance(self):
        sched = self.makeScheduler(name='n', builderNames=['k'])
        new_sched = self.makeScheduler(name='n', builderNames=['l'])
        distractor = self.makeScheduler(name='x', builderNames=['l'])
        config = mock.Mock()
        config.schedulers = dict(dist=distractor, n=new_sched)
        self.assertIdentical(sched.findNewSchedulerInstance(config), new_sched)
