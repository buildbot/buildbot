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

import re
import os
import mock
import signal
from twisted.internet import defer, reactor, task
from twisted.trial import unittest
from twisted.python import log
from buildbot import master, monkeypatches, config
from buildbot.db import exceptions
from buildbot.test.util import dirs, compat
from buildbot.test.fake import fakedb, fakemq
from buildbot.util import epoch2datetime
from buildbot.process.users import users
from buildbot.status.results import SUCCESS

class GlobalMessages(dirs.DirsMixin, unittest.TestCase):

    """These tests coerce the master into performing some action that should be
    accompanied by some messages, and then verifies that the messages were sent
    appropriately.  Like most tests in this file, this requires faking out a
    *lot* of Buildbot."""

    def setUp(self):
        basedir = os.path.abspath('basedir')
        d = self.setUpDirs(basedir)
        def set_master(_):
            self.master = master.BuildMaster(basedir)
            self.master.db = fakedb.FakeDBConnector(self)
            self.master.mq = fakemq.FakeMQConnector(self)
        d.addCallback(set_master)
        return d

    def tearDown(self):
        return self.tearDownDirs()

    # master.$masterid.{started,stopped} are checked in
    # StartupAndReconfig.test_startup_ok, below

    def test_change_message(self):
        d = self.master.addChange(author='warner', branch='warnerdb',
                category='devel', comments='fix whitespace',
                files=[u'master/buildbot/__init__.py'],
                project='Buildbot', properties={},
                repository='git://warner', revision='0e92a098b',
                revlink='http://warner/0e92a098b',
                when_timestamp=epoch2datetime(256738404))
        def check(change):
            # check the correct message was received
            self.assertEqual(self.master.mq.productions, [
                ( ('change', '500', 'new'), {
                    'author': u'warner',
                    'branch': u'warnerdb',
                    'category': u'devel',
                    'codebase': '',
                    'comments': u'fix whitespace',
                    'changeid' : change.number,
                    'files': [u'master/buildbot/__init__.py'],
                    'is_dir': 0,
                    'project': u'Buildbot',
                    'properties': {},
                    'repository': u'git://warner',
                    'revision': u'0e92a098b',
                    'revlink': u'http://warner/0e92a098b',
                    'when_timestamp': 256738404,
                })
            ])
        d.addCallback(check)
        return d

    def test_buildset_messages(self):
        sourcestampsetid=111

        d = self.master.addBuildset(scheduler='schname',
                sourcestampsetid=sourcestampsetid,
                reason='rsn', properties={},
                builderNames=['a', 'b'], external_idstring='eid')
        def check((bsid,brids)):
            # addBuildset returned the expected values (these come from fakedb)
            self.assertEqual((bsid,brids), (200, dict(a=1000,b=1001)))

            # check that the proper message was produced
            self.assertEqual(sorted(self.master.mq.productions), sorted([
                ( ('buildset', '200', 'new'), {
                    'bsid': bsid,
                    'external_idstring': 'eid',
                    'reason': 'rsn',
                    'sourcestampsetid': sourcestampsetid,
                    'brids': dict(a=1000, b=1001),
                    'properties': {},
                    'scheduler': 'schname',
                }),
                ( ('buildrequest', '200', '-1', '1000', 'new'), {
                    'brid': 1000,
                    'bsid': 200,
                    'buildername': 'a',
                    'builderid': -1,
                }),
                ( ('buildrequest', '200', '-1', '1001', 'new'), {
                    'brid': 1001,
                    'bsid': 200,
                    'buildername': 'b',
                    'builderid': -1,
                }),
            ]))
        d.addCallback(check)
        return d

    def test_buildset_completion_messages(self):
        self.master.db.insertTestData([
            fakedb.SourceStamp(id=999),
            fakedb.BuildRequest(id=300, buildsetid=440, complete=True,
                results=SUCCESS),
            fakedb.BuildRequest(id=301, buildsetid=440, complete=True,
                results=SUCCESS),
            fakedb.Buildset(id=440, sourcestampsetid=999),
        ])

        clock = task.Clock()
        clock.advance(1234)
        self.master.maybeBuildsetComplete(440, _reactor=clock)

        self.assertEqual(self.master.mq.productions, [
            ( ('buildset', '440', 'complete'), {
                'bsid': 440,
                'complete_at': 1234,
                'results': SUCCESS,
            }),
        ])


class AddChange(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        basedir = os.path.abspath('basedir')
        d = self.setUpDirs(basedir)
        def set_master(_):
            self.master = master.BuildMaster(basedir)
            self.master.mq = fakemq.FakeMQConnector(self)
        d.addCallback(set_master)
        return d

    def tearDown(self):
        return self.tearDownDirs()

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


class StartupAndReconfig(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basedir')
        d = self.setUpDirs(self.basedir)
        @d.addCallback
        def make_master(_):
            # don't create child services
            self.patch(master.BuildMaster, 'create_child_services',
                    lambda self : None)

            # patch out a few other annoying things the msater likes to do
            self.patch(monkeypatches, 'patch_all', lambda : None)
            self.patch(signal, 'signal', lambda sig, hdlr : None)
            self.patch(master, 'Status', lambda master : mock.Mock()) # XXX temporary
            self.patch(config.MasterConfig, 'loadConfig',
                    classmethod(lambda cls, b, f : cls()))

            self.master = master.BuildMaster(self.basedir)
            self.db = self.master.db = fakedb.FakeDBConnector(self)
            self.mq = self.master.mq = fakemq.FakeMQConnector(self)

        @d.addCallback
        def patch_log_msg(_):
            msg = mock.Mock(side_effect=log.msg)
            self.patch(log, 'msg', msg)

        return d

    def tearDown(self):
        return self.tearDownDirs()

    def make_reactor(self):
        r = mock.Mock()
        r.callWhenRunning = reactor.callWhenRunning
        return r

    def assertLogged(self, regexp):
        r = re.compile(regexp)
        for args, kwargs in log.msg.call_args_list:
            if args and r.search(args[0]):
                return
        self.fail("%r not matched in log output" % regexp)

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
        d.addCallback(lambda _ : self.master.stopService())

        @d.addCallback
        def check(_):
            reactor.stop.assert_called()
            self.assertLogged("oh noes")
        return d

    def test_startup_db_not_ready(self):
        reactor = self.make_reactor()
        def db_setup():
            log.msg("GOT HERE")
            raise exceptions.DatabaseNotReadyError()
        self.db.setup = db_setup

        d = self.master.startService(_reactor=reactor)
        d.addCallback(lambda _ : self.master.stopService())

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
        d.addCallback(lambda _ : self.master.stopService())

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

            # check started/stopped messages
            self.assertEqual(self.master.mq.productions, [
                ( ('master', '100', 'started'), {
                    'master_basedir': self.basedir,
                    'master_hostname': self.master.hostname,
                    'masterid': 100,
                }),
                ( ('master', '100', 'stopped'), {
                    'master_basedir': self.basedir,
                    'master_hostname': self.master.hostname,
                    'masterid': 100,
                }),
                ])
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

    def test_reconfigService_db_url_changed(self):
        old = self.master.config = config.MasterConfig()
        old.db['db_url'] = 'aaaa'
        new = config.MasterConfig()
        new.db['db_url'] = 'bbbb'

        self.assertRaises(config.ConfigErrors, lambda :
            self.master.reconfigService(new))
