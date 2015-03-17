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

import os
import mock
import signal
from twisted.internet import defer, reactor, task
from twisted.trial import unittest
from twisted.python import log
from buildbot import master, monkeypatches, config
from buildbot.util import subscription
from buildbot.db import connector
from buildbot.test.util import dirs, compat, misc, logging
from buildbot.test.fake import fakedb
from buildbot.util import epoch2datetime
from buildbot.changes import changes
from buildbot.process.users import users

class Subscriptions(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        basedir = os.path.abspath('basedir')
        d = self.setUpDirs(basedir)
        def set_master(_):
            self.master = master.BuildMaster(basedir)
            self.master.config.db['db_poll_interval'] = None
        d.addCallback(set_master)
        return d

    def tearDown(self):
        return self.tearDownDirs()
        
    def test_change_subscription(self):
        changeid = 918
        chdict = {
            'changeid': 14,
            'author': u'warner',
            'branch': u'warnerdb',
            'category': u'devel',
            'comments': u'fix whitespace',
            'files': [u'master/buildbot/__init__.py'],
            'is_dir': 0,
            'project': u'Buildbot',
            'properties': {},
            'repository': u'git://warner',
            'revision': u'0e92a098b',
            'revlink': u'http://warner/0e92a098b',
            'when_timestamp': epoch2datetime(266738404),
        }
        newchange = mock.Mock(name='newchange')

        # patch out everything we're about to call
        self.master.db = mock.Mock()
        self.master.db.changes.addChange.return_value = \
            defer.succeed(changeid)
        self.master.db.changes.getChange.return_value = \
            defer.succeed(chdict)
        self.patch(changes.Change, 'fromChdict',
                classmethod(lambda cls, master, chdict :
                                defer.succeed(newchange)))

        cb = mock.Mock()
        sub = self.master.subscribeToChanges(cb)
        self.assertIsInstance(sub, subscription.Subscription)

        d = self.master.addChange()
        def check(change):
            # master called the right thing in the db component, including with
            # appropriate default values
            self.master.db.changes.addChange.assert_called_with(author=None,
                    files=None, comments=None, is_dir=0,
                    revision=None, when_timestamp=None, branch=None, codebase='',
                    category=None, revlink='', properties={}, repository='', project='', uid=None)

            self.master.db.changes.getChange.assert_called_with(changeid)
            # addChange returned the right value
            self.failUnless(change is newchange) # fromChdict's return value
            # and the notification sub was called correctly
            cb.assert_called_with(newchange)
        d.addCallback(check)
        return d

    def do_test_addChange_args(self, args=(), kwargs={}, exp_db_kwargs={}):
        # add default arguments
        default_db_kwargs = dict(files=None, comments=None, author=None,
                is_dir=0, revision=None, when_timestamp=None,
                branch=None, category=None, revlink='', properties={},
                repository='', codebase='', project='', uid=None)
        k = default_db_kwargs
        k.update(exp_db_kwargs)
        exp_db_kwargs = k

        self.master.db = mock.Mock()
        got = []
        def db_addChange(*args, **kwargs):
            got[:] = args, kwargs
            # use an exception as a quick way to bail out of the remainder
            # of the addChange method
            return defer.fail(RuntimeError)
        self.master.db.changes.addChange = db_addChange

        d = self.master.addChange(*args, **kwargs)
        d.addCallback(lambda _ : self.fail("should not succeed"))
        def check(f):
            self.assertEqual(got, [(), exp_db_kwargs])
        d.addErrback(check)
        return d

    def test_addChange_args_author(self):
        # who should come through as author
        return self.do_test_addChange_args(
                kwargs=dict(who='me'),
                exp_db_kwargs=dict(author='me'))

    def test_addChange_args_isdir(self):
        # isdir should come through as is_dir
        return self.do_test_addChange_args(
                kwargs=dict(isdir=1),
                exp_db_kwargs=dict(is_dir=1))

    def test_addChange_args_when(self):
        # when should come through as when_timestamp, as a datetime
        return self.do_test_addChange_args(
                kwargs=dict(when=892293875),
                exp_db_kwargs=dict(when_timestamp=epoch2datetime(892293875)))

    def test_addChange_args_properties(self):
        # properties should be qualified with a source
        return self.do_test_addChange_args(
                kwargs=dict(properties={ 'a' : 'b' }),
                exp_db_kwargs=dict(properties={ 'a' : ('b', 'Change') }))

    def test_addChange_args_properties_tuple(self):
        # properties should be qualified with a source, even if they
        # already look like they have a source
        return self.do_test_addChange_args(
                kwargs=dict(properties={ 'a' : ('b', 'Change') }),
                exp_db_kwargs=dict(properties={
                    'a' : (('b', 'Change'), 'Change') }))

    def test_addChange_args_positional(self):
        # master.addChange can take author, files, comments as positional
        # arguments
        return self.do_test_addChange_args(
                args=('me', ['a'], 'com'),
                exp_db_kwargs=dict(author='me', files=['a'], comments='com'))
                
    def do_test_createUserObjects_args(self, args=(), kwargs={}, exp_args=()):
        got = []
        def fake_createUserObject(*args, **kwargs):
            got[:] = args, kwargs
            # use an exception as a quick way to bail out of the remainder
            # of the createUserObject method
            return defer.fail(RuntimeError)

        self.patch(users, 'createUserObject', fake_createUserObject)

        d = self.master.addChange(*args, **kwargs)
        d.addCallback(lambda _ : self.fail("should not succeed"))
        def check(f):
            self.assertEqual(got, [exp_args, {}])
        d.addErrback(check)
        return d

    def test_addChange_createUserObject_args(self):
        # who should come through as author
        return self.do_test_createUserObjects_args(
                kwargs=dict(who='me', src='git'),
                exp_args=(self.master, 'me', 'git'))
               
    def test_buildset_subscription(self):
        self.master.db = mock.Mock()
        self.master.db.buildsets.addBuildset.return_value = \
            defer.succeed((938593, dict(a=19,b=20)))

        cb = mock.Mock()
        sub = self.master.subscribeToBuildsets(cb)
        self.assertIsInstance(sub, subscription.Subscription)

        d = self.master.addBuildset(ssid=999)
        def check((bsid,brids)):
            # master called the right thing in the db component
            self.master.db.buildsets.addBuildset.assert_called_with(ssid=999)
            # addBuildset returned the right value
            self.assertEqual((bsid,brids), (938593, dict(a=19,b=20)))
            # and the notification sub was called correctly
            cb.assert_called_with(bsid=938593, ssid=999)
        d.addCallback(check)
        return d

    def test_buildset_completion_subscription(self):
        self.master.db = mock.Mock()

        cb = mock.Mock()
        sub = self.master.subscribeToBuildsetCompletions(cb)
        self.assertIsInstance(sub, subscription.Subscription)

        self.master._buildsetComplete(938593, 999)
        # assert the notification sub was called correctly
        cb.assert_called_with(938593, 999)

class StartupAndReconfig(dirs.DirsMixin, logging.LoggingMixin, unittest.TestCase):

    def setUp(self):
        self.setUpLogging()
        self.basedir = os.path.abspath('basedir')
        d = self.setUpDirs(self.basedir)
        @d.addCallback
        def make_master(_):
            # don't create child services
            self.patch(master.BuildMaster, 'create_child_services',
                    lambda self : None)

            # patch out a few other annoying things the master likes to do
            self.patch(monkeypatches, 'patch_all', lambda : None)
            self.patch(signal, 'signal', lambda sig, hdlr : None)
            self.patch(master, 'Status', lambda master : mock.Mock()) # XXX temporary
            self.patch(config.MasterConfig, 'loadConfig',
                    classmethod(lambda cls, b, f : cls()))

            self.master = master.BuildMaster(self.basedir)
            self.db = self.master.db = fakedb.FakeDBConnector(self)

        return d

    def tearDown(self):
        return self.tearDownDirs()

    def make_reactor(self):
        r = mock.Mock()
        r.callWhenRunning = reactor.callWhenRunning
        return r

    def patch_loadConfig_fail(self):
        @classmethod
        def loadConfig(cls, b, f):
            config.error('oh noes')
        self.patch(config.MasterConfig, 'loadConfig', loadConfig)


    # tests

    def test_startup_bad_config(self):
        reactor = self.make_reactor()
        self.patch_loadConfig_fail()

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check(_):
            reactor.stop.assert_called()
            self.assertLogged("oh noes")
        return d

    def test_startup_db_not_ready(self):
        reactor = self.make_reactor()
        def db_setup():
            log.msg("GOT HERE")
            raise connector.DatabaseNotReadyError()
        self.db.setup = db_setup

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check(_):
            reactor.stop.assert_called()
            self.assertLogged("GOT HERE")
        return d

    @compat.usesFlushLoggedErrors
    def test_startup_error(self):
        reactor = self.make_reactor()
        def db_setup():
            raise RuntimeError("oh noes")
        self.db.setup = db_setup

        d = self.master.startService(_reactor=reactor)

        @d.addCallback
        def check(_):
            reactor.stop.assert_called()
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        return d

    def test_startup_ok(self):
        reactor = self.make_reactor()

        d = self.master.startService(_reactor=reactor)
        d.addCallback(lambda _ : self.master.stopService())

        @d.addCallback
        def check(_):
            self.failIf(reactor.stop.called)
            self.assertLogged("BuildMaster is running")
        return d

    def test_reconfig(self):
        reactor = self.make_reactor()
        self.master.reconfigService = mock.Mock(
                side_effect=lambda n : defer.succeed(None))

        d = self.master.startService(_reactor=reactor)
        d.addCallback(lambda _ : self.master.reconfig())
        d.addCallback(lambda _ : self.master.stopService())

        @d.addCallback
        def check(_):
            self.master.reconfigService.assert_called()
        return d

    @defer.inlineCallbacks
    def test_reconfig_bad_config(self):
        reactor = self.make_reactor()
        self.master.reconfigService = mock.Mock(
                side_effect=lambda n : defer.succeed(None))

        yield self.master.startService(_reactor=reactor)

        # reset, since startService called reconfigService
        self.master.reconfigService.reset_mock()

        # reconfig, with a failure
        self.patch_loadConfig_fail()
        yield self.master.reconfig()

        self.master.stopService()

        self.assertLogged("reconfig aborted without")
        self.failIf(self.master.reconfigService.called)

    @defer.inlineCallbacks
    def test_reconfigService_db_url_changed(self):
        old = self.master.config = config.MasterConfig()
        old.db['db_url'] = 'aaaa'
        yield self.master.reconfigService(old)

        new = config.MasterConfig()
        new.db['db_url'] = 'bbbb'

        self.assertRaises(config.ConfigErrors, lambda :
                self.master.reconfigService(new))

    def test_reconfigService_start_polling(self):
        loopingcall = mock.Mock()
        self.patch(task, 'LoopingCall', lambda fn : loopingcall)

        self.master.config = config.MasterConfig()
        new = config.MasterConfig()
        new.db['db_poll_interval'] = 120

        d = self.master.reconfigService(new)
        @d.addCallback
        def check(_):
            loopingcall.start.assert_called_with(120, now=False)
        return d

    @defer.inlineCallbacks
    def test_reconfigService_stop_polling(self):
        db_loop = self.master.db_loop = mock.Mock()

        old = self.master.config = config.MasterConfig()
        old.db['db_poll_interval'] = 120
        yield self.master.reconfigService(old)

        new = config.MasterConfig()
        new.db['db_poll_interval'] = None
        yield self.master.reconfigService(new)

        db_loop.stop.assert_called()
        self.assertEqual(self.master.db_loop, None)


class Polling(dirs.DirsMixin, misc.PatcherMixin, unittest.TestCase):

    def setUp(self):
        self.gotten_changes = []
        self.gotten_buildset_additions = []
        self.gotten_buildset_completions = []
        self.gotten_buildrequest_additions = []


        basedir = os.path.abspath('basedir')

        # patch out os.uname so that we get a consistent hostname
        self.patch_os_uname(lambda : [ 0, 'testhost.localdomain' ])
        self.master_name = "testhost.localdomain:%s" % (basedir,)

        d = self.setUpDirs(basedir)
        def set_master(_):
            self.master = master.BuildMaster(basedir)

            self.db = self.master.db = fakedb.FakeDBConnector(self)

            self.master.config.db['db_poll_interval'] = 10

            # overridesubscription callbacks
            self.master._change_subs = sub = mock.Mock()
            sub.deliver = self.deliverChange
            self.master._new_buildset_subs = sub = mock.Mock()
            sub.deliver = self.deliverBuildsetAddition
            self.master._complete_buildset_subs = sub = mock.Mock()
            sub.deliver = self.deliverBuildsetCompletion
            self.master._new_buildrequest_subs = sub = mock.Mock()
            sub.deliver = self.deliverBuildRequestAddition

        d.addCallback(set_master)
        return d

    def tearDown(self):
        return self.tearDownDirs()

    def deliverChange(self, change):
        self.gotten_changes.append(change)

    def deliverBuildsetAddition(self, **kwargs):
        self.gotten_buildset_additions.append(kwargs)

    def deliverBuildsetCompletion(self, bsid, result):
        self.gotten_buildset_completions.append((bsid, result))

    def deliverBuildRequestAddition(self, notif):
        self.gotten_buildrequest_additions.append(notif)

    # tests

    def test_pollDatabaseChanges_empty(self):
        self.db.insertTestData([
            fakedb.Object(id=22, name=self.master_name,
                          class_name='buildbot.master.BuildMaster'),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual(self.gotten_changes, [])
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(22, last_processed_change=0)
        d.addCallback(check)
        return d

    def test_pollDatabaseChanges_catchup(self):
        # with no existing state, it should catch up to the most recent change,
        # but not process anything
        self.db.insertTestData([
            fakedb.Object(id=22, name=self.master_name,
                          class_name='buildbot.master.BuildMaster'),
            fakedb.Change(changeid=10),
            fakedb.Change(changeid=11),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual(self.gotten_changes, [])
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(22, last_processed_change=11)
        d.addCallback(check)
        return d

    def test_pollDatabaseChanges_multiple(self):
        self.db.insertTestData([
            fakedb.Object(id=53, name=self.master_name,
                          class_name='buildbot.master.BuildMaster'),
            fakedb.ObjectState(objectid=53, name='last_processed_change',
                               value_json='10'),
            fakedb.Change(changeid=10),
            fakedb.Change(changeid=11),
            fakedb.Change(changeid=12),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual([ ch.number for ch in self.gotten_changes],
                             [ 11, 12 ]) # note 10 was already seen
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(53, last_processed_change=12)
        d.addCallback(check)
        return d

    def test_pollDatabaseChanges_nothing_new(self):
        self.db.insertTestData([
            fakedb.Object(id=53, name='master',
                          class_name='buildbot.master.BuildMaster'),
            fakedb.ObjectState(objectid=53, name='last_processed_change',
                               value_json='10'),
            fakedb.Change(changeid=10),
        ])
        d = self.master.pollDatabaseChanges()
        def check(_):
            self.assertEqual(self.gotten_changes, [])
            self.assertEqual(self.gotten_buildset_additions, [])
            self.assertEqual(self.gotten_buildset_completions, [])
            self.db.state.assertState(53, last_processed_change=10)
        d.addCallback(check)
        return d

    def test_pollDatabaseBuildRequests_empty(self):
        d = self.master.pollDatabaseBuildRequests()
        def check(_):
            self.assertEqual(self.gotten_buildrequest_additions, [])
        d.addCallback(check)
        return d

    def test_pollDatabaseBuildRequests_new(self):
        self.db.insertTestData([
            fakedb.SourceStampSet(id=127),
            fakedb.SourceStamp(id=127, sourcestampsetid=127),
            fakedb.Buildset(id=99, sourcestampsetid=127),
            fakedb.BuildRequest(id=19, buildsetid=99, buildername='9teen'),
            fakedb.BuildRequest(id=20, buildsetid=99, buildername='twenty')
        ])
        d = self.master.pollDatabaseBuildRequests()
        def check(_):
            self.assertEqual(sorted(self.gotten_buildrequest_additions),
                    sorted([dict(bsid=99, brid=19, buildername='9teen'),
                            dict(bsid=99, brid=20, buildername='twenty')]))
        d.addCallback(check)
        return d

    def test_pollDatabaseBuildRequests_incremental(self):
        d = defer.succeed(None)
        def insert1(_):
            self.db.insertTestData([
            fakedb.SourceStampSet(id=127),
            fakedb.SourceStamp(id=127, sourcestampsetid=127),
            fakedb.Buildset(id=99, sourcestampsetid=127),
            fakedb.BuildRequest(id=11, buildsetid=9, buildername='eleventy'),
            ])
        d.addCallback(insert1)
        d.addCallback(lambda _ : self.master.pollDatabaseBuildRequests())
        def insert2_and_claim(_):
            self.gotten_buildrequest_additions.append('MARK')
            self.db.insertTestData([
                fakedb.BuildRequest(id=20, buildsetid=9,
                                        buildername='twenty'),
            ])
            self.db.buildrequests.fakeClaimBuildRequest(11)
        d.addCallback(insert2_and_claim)
        d.addCallback(lambda _ : self.master.pollDatabaseBuildRequests())
        def unclaim(_):
            self.gotten_buildrequest_additions.append('MARK')
            self.db.buildrequests.fakeUnclaimBuildRequest(11)
            # note that at this point brid 20 is still unclaimed, but we do
            # not get a new notification about it
        d.addCallback(unclaim)
        d.addCallback(lambda _ : self.master.pollDatabaseBuildRequests())
        def check(_):
            self.assertEqual(self.gotten_buildrequest_additions, [
                dict(bsid=9, brid=11, buildername='eleventy'),
                'MARK',
                dict(bsid=9, brid=20, buildername='twenty'),
                'MARK',
                dict(bsid=9, brid=11, buildername='eleventy'),
            ])
        d.addCallback(check)
        return d

