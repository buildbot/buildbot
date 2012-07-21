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

    # tests

    def test_constructor_builderNames(self):
        self.assertRaises(config.ConfigErrors,
                lambda : self.makeScheduler(builderNames='xxx'))

    def test_constructor_builderNames_unicode(self):
        self.makeScheduler(builderNames=[u'a'])

    def test_constructor_codebases_valid(self):
        codebases = {"codebase1": {"repository":"", "branch":"", "revision":""}}
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
        d = sched.addBuildsetForLatest(reason='because')
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='because', brids=brids,
                        external_idstring=None,
                        properties=[ ('a', ('b', 'Scheduler')),
                                     ('scheduler', ('testy', 'Scheduler')), ],
                        sourcestampsetid=100),
                    {'':
                     dict(branch=None, revision=None, repository='', codebase='',
                         project='', sourcestampsetid=100)
                    })
        d.addCallback(check)
        return d

    def test_startConsumingChanges_fileIsImportant_check(self):
        sched = self.makeScheduler()
        self.assertRaises(AssertionError,
                lambda : sched.startConsumingChanges(fileIsImportant="maybe"))

    def do_test_change_consumption(self, kwargs, change, expected_result):
        # (expected_result should be True (important), False (unimportant), or
        # None (ignore the change))
        sched = self.makeScheduler()
        sched.startService()

        change_received = [ None ]
        def gotChange(got_change, got_important):
            self.assertEqual(got_change, change)
            change_received[0] = got_important
            return defer.succeed(None)
        sched.gotChange = gotChange

        d = sched.startConsumingChanges(**kwargs)
        def test(_):
            # check that it registered a callback
            callbacks = self.master.getSubscriptionCallbacks()
            self.assertNotEqual(callbacks['changes'], None)

            # invoke the callback with the change, and check the result
            callbacks['changes'](change)
            self.assertEqual(change_received[0], expected_result)
        d.addCallback(test)
        d.addCallback(lambda _ : sched.stopService())
        return d

    def test_change_consumption_defaults(self):
        # all changes are important by default
        return self.do_test_change_consumption(
                dict(),
                self.makeFakeChange(),
                True)

    def test_change_consumption_fileIsImportant_True(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : True),
                self.makeFakeChange(),
                True)

    def test_change_consumption_fileIsImportant_False(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : False),
                self.makeFakeChange(),
                False)

    def test_change_consumption_fileIsImportant_exception(self):
        d = self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : 1/0),
                self.makeFakeChange(),
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
                self.makeFakeChange(),
                True)

    def test_change_consumption_change_filter_False(self):
        cf = mock.Mock()
        cf.filter_change = lambda c : False
        return self.do_test_change_consumption(
                dict(change_filter=cf),
                self.makeFakeChange(),
                None)

    def test_change_consumption_fileIsImportant_False_onlyImportant(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : False, onlyImportant=True),
                self.makeFakeChange(),
                None)

    def test_change_consumption_fileIsImportant_True_onlyImportant(self):
        return self.do_test_change_consumption(
                dict(fileIsImportant=lambda c : True, onlyImportant=True),
                self.makeFakeChange(),
                True)

    def test_addBuilsetForLatest_args(self):
        sched = self.makeScheduler(name='xyz', builderNames=['y', 'z'])
        d = sched.addBuildsetForLatest(reason='cuz', branch='default',
                    project='myp', repository='hgmo',
                    external_idstring='try_1234')
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='cuz', brids=brids,
                        external_idstring='try_1234',
                        properties=[('scheduler', ('xyz', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='default', revision=None, repository='hgmo',
                          codebase='', project='myp', sourcestampsetid=100)
                    })
        d.addCallback(check)
        return d

    def test_addBuildsetForLatest_properties(self):
        props = properties.Properties(xxx="yyy")
        sched = self.makeScheduler(name='xyz', builderNames=['y', 'z'])
        d = sched.addBuildsetForLatest(reason='cuz', branch='default',
                    project='myp', repository='hgmo',
                    external_idstring='try_1234', properties=props)
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='cuz', brids=brids,
                        external_idstring='try_1234',
                        properties=[
                            ('scheduler', ('xyz', 'Scheduler')),
                            ('xxx', ('yyy', 'TEST')),
                        ],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='default', revision=None, repository='hgmo',
                          codebase='', project='myp', sourcestampsetid=100)
                    })
        d.addCallback(check)
        return d

    def test_addBuildsetForLatest_builderNames(self):
        sched = self.makeScheduler(name='xyz', builderNames=['y', 'z'])
        d = sched.addBuildsetForLatest(reason='cuz', branch='default',
                    builderNames=['a', 'b'])
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='cuz', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('xyz', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='default', revision=None, repository='',
                          codebase='', project='', sourcestampsetid=100)
                    })
        d.addCallback(check)
        return d

    def test_addBuildsetForChanges_one_change(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                            repository='svn://...', codebase='',
                            project='world-domination'),
        ])
        d = sched.addBuildsetForChanges(reason='power', changeids=[13])
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='power', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='trunk', repository='svn://...', codebase='',
                        changeids=set([13]), project='world-domination',
                        revision='9283', sourcestampsetid=100)
                    })
        d.addCallback(check)
        return d

    def test_addBuildsetForChanges_properties(self):
        props = properties.Properties(xxx="yyy")
        sched = self.makeScheduler(name='n', builderNames=['c'])
        self.db.insertTestData([
            fakedb.Change(changeid=14, branch='default', revision='123:abc',
                            repository='', project='', codebase=''),
        ])
        d = sched.addBuildsetForChanges(reason='downstream', changeids=[14],
                            properties=props)
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='downstream', brids=brids,
                        external_idstring=None,
                        properties=[
                            ('scheduler', ('n', 'Scheduler')),
                            ('xxx', ('yyy', 'TEST')),
                        ],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='default', revision='123:abc', repository='',
                         project='', changeids=set([14]), sourcestampsetid=100,
                         codebase='')
                    })
        d.addCallback(check)
        return d

    def test_addBuildsetForChanges_one_change_builderNames(self):
        sched = self.makeScheduler(name='n', builderNames=['b'])
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                          codebase='', repository='svn://...', 
                          project='world-domination'),
        ])
        d = sched.addBuildsetForChanges(reason='power', changeids=[13],
                            builderNames=['p'])
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='power', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='trunk', repository='svn://...', codebase='',
                         changeids=set([13]), project='world-domination',
                         revision='9283', sourcestampsetid=100)
                    })
        d.addCallback(check)
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
        d = sched.addBuildsetForChanges(reason='power', changeids=[14, 15, 13])
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='power', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='trunk', repository='svn://C..', codebase='',
                        changeids=set([13,14,15]), project='world-domination',
                        revision='9285', sourcestampsetid=100)
                    })
        d.addCallback(check)
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
        d = sched.addBuildsetForChanges(reason='power', changeids=[14, 15, 13])
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='power', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'':
                     dict(branch='trunk', repository='svn://...', codebase='',
                        changeids=set([13,14,15]), project='world-domination',
                        revision='9285', sourcestampsetid=100)
                    })
        d.addCallback(check)
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
        d = sched.addBuildsetForChanges(reason='power', changeids=[14, 12, 17, 16, 13, 15])
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='power', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=100),
                    {'cbA':
                     dict(branch='develop', repository='svn://A..', codebase='cbA',
                        changeids=set([12,13,14]), project='making-tea',
                        revision='9284', sourcestampsetid=100),
                    'cbB':
                     dict(branch='develop', repository='svn://B..', codebase='cbB',
                        changeids=set([15,16,17]), project='swimming',
                        revision='8087', sourcestampsetid=100),
                    'cbC':
                     dict(branch='stable', repository='svn://C..', codebase='cbC',
                        project='', revision='12345', sourcestampsetid=100),
                    'cbD':
                     dict(branch=None, repository='svn://D..', codebase='cbD',
                        project='', revision=None, sourcestampsetid=100),
                    })
        d.addCallback(check)
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
                sched.addBuildsetForSourceStamp(reason='whynot', setid=1091))
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='whynot', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=1091),
                    {'':
                     dict(branch='fixins', revision='abc', repository='r',
                         project='p', codebase='', sourcestampsetid=1091)
                    })
        d.addCallback(check)
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
            sched.addBuildsetForSourceStamp(reason='whynot', setid=1091,
                                            properties=props))
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='whynot', brids=brids,
                        external_idstring=None,
                        properties=[
                            ('scheduler', ('n', 'Scheduler')),
                            ('xxx', ('yyy', 'TEST')),
                        ],
                        sourcestampsetid=1091),
                    {'cb':
                     dict(branch='fixins', revision='abc', repository='r',
                          codebase='cb', project='p', sourcestampsetid=1091)
                    })
        d.addCallback(check)
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
            sched.addBuildsetForSourceStamp(reason='whynot', setid = 1091,
                        builderNames=['a', 'b']))
        def check((bsid,brids)):
            self.db.buildsets.assertBuildset(bsid,
                    dict(reason='whynot', brids=brids,
                        external_idstring=None,
                        properties=[('scheduler', ('n', 'Scheduler'))],
                        sourcestampsetid=1091),
                    {'cb':
                     dict(branch='fixins', revision='abc', repository='r',
                         codebase='cb', project='p', sourcestampsetid=1091)
                    })
        d.addCallback(check)
        return d

    def test_findNewSchedulerInstance(self):
        sched = self.makeScheduler(name='n', builderNames=['k'])
        new_sched = self.makeScheduler(name='n', builderNames=['l'])
        distractor = self.makeScheduler(name='x', builderNames=['l'])
        config = mock.Mock()
        config.schedulers = dict(dist=distractor, n=new_sched)
        self.assertIdentical(sched.findNewSchedulerInstance(config), new_sched)
