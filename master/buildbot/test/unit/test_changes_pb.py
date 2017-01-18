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
from twisted.trial import unittest

from buildbot import config
from buildbot.changes import pb
from buildbot.test.fake import fakemaster
from buildbot.test.util import changesource
from buildbot.test.util import pbmanager


class TestPBChangeSource(
    changesource.ChangeSourceMixin,
    pbmanager.PBManagerMixin,
        unittest.TestCase):

    DEFAULT_CONFIG = dict(port='9999',
                          user='alice',
                          passwd='sekrit',
                          name=changesource.ChangeSourceMixin.DEFAULT_NAME)

    EXP_DEFAULT_REGISTRATION = ('9999', 'alice', 'sekrit')

    def setUp(self):
        self.setUpPBChangeSource()
        d = self.setUpChangeSource()

        @d.addCallback
        def setup(_):
            self.master.pbmanager = self.pbmanager

        return d

    def test_registration_no_workerport(self):
        return self._test_registration(None, exp_ConfigErrors=True,
                                       user='alice', passwd='sekrit')

    def test_registration_global_workerport(self):
        return self._test_registration(self.EXP_DEFAULT_REGISTRATION,
                                       **self.DEFAULT_CONFIG)

    def test_registration_custom_port(self):
        return self._test_registration(('8888', 'alice', 'sekrit'),
                                       user='alice', passwd='sekrit', port='8888')

    def test_registration_no_userpass(self):
        return self._test_registration(('9939', 'change', 'changepw'),
                                       workerPort='9939')

    def test_registration_no_userpass_no_global(self):
        return self._test_registration(None, exp_ConfigErrors=True)

    def test_no_registration_if_master_already_claimed(self):
        # claim the CS on another master...
        self.setChangeSourceToMaster(self.OTHER_MASTER_ID)
        # and then use the same args as one of the above success cases,
        # but expect that it will NOT register
        return self._test_registration(None, **self.DEFAULT_CONFIG)

    def test_registration_later_if_master_can_do_it(self):
        # get the changesource running but not active due to the other master
        self.setChangeSourceToMaster(self.OTHER_MASTER_ID)
        self.attachChangeSource(pb.PBChangeSource(**self.DEFAULT_CONFIG))
        self.startChangeSource()
        self.assertNotRegistered()

        # other master goes away
        self.setChangeSourceToMaster(None)

        # not quite enough time to cause it to activate
        self.changesource.clock.advance(
            self.changesource.POLL_INTERVAL_SEC * 4 / 5)
        self.assertNotRegistered()

        # there we go!
        self.changesource.clock.advance(
            self.changesource.POLL_INTERVAL_SEC * 2 / 5)
        self.assertRegistered(*self.EXP_DEFAULT_REGISTRATION)

    @defer.inlineCallbacks
    def _test_registration(self, exp_registration, exp_ConfigErrors=False,
                           workerPort=None, **constr_kwargs):
        cfg = mock.Mock()
        cfg.protocols = {'pb': {'port': workerPort}}
        self.attachChangeSource(pb.PBChangeSource(**constr_kwargs))

        self.startChangeSource()
        if exp_ConfigErrors:
            # if it's not registered, it should raise a ConfigError.
            try:
                yield self.changesource.reconfigServiceWithBuildbotConfig(cfg)
            except config.ConfigErrors:
                pass
            else:
                self.fail("Expected ConfigErrors")
        else:
            yield self.changesource.reconfigServiceWithBuildbotConfig(cfg)

        if exp_registration:
            self.assertRegistered(*exp_registration)

        yield self.stopChangeSource()

        if exp_registration:
            self.assertUnregistered(*exp_registration)
        self.assertEqual(self.changesource.registration, None)

    def test_perspective(self):
        self.attachChangeSource(
            pb.PBChangeSource('alice', 'sekrit', port='8888'))
        persp = self.changesource.getPerspective(mock.Mock(), 'alice')
        self.assertIsInstance(persp, pb.ChangePerspective)

    def test_describe(self):
        cs = pb.PBChangeSource()
        self.assertSubstring("PBChangeSource", cs.describe())

    def test_name(self):
        cs = pb.PBChangeSource(port=1234)
        self.assertEqual("PBChangeSource:1234", cs.name)

        cs = pb.PBChangeSource(port=1234, prefix="pre")
        self.assertEqual("PBChangeSource:pre:1234", cs.name)

        # explicit name:
        cs = pb.PBChangeSource(name="MyName")
        self.assertEqual("MyName", cs.name)

    def test_describe_prefix(self):
        cs = pb.PBChangeSource(prefix="xyz")
        self.assertSubstring("PBChangeSource", cs.describe())
        self.assertSubstring("xyz", cs.describe())

    def test_describe_int(self):
        cs = pb.PBChangeSource(port=9989)
        self.assertSubstring("PBChangeSource", cs.describe())

    @defer.inlineCallbacks
    def test_reconfigService_no_change(self):
        config = mock.Mock()
        self.attachChangeSource(pb.PBChangeSource(port='9876'))

        self.startChangeSource()
        yield self.changesource.reconfigServiceWithBuildbotConfig(config)

        self.assertRegistered('9876', 'change', 'changepw')

        yield self.stopChangeSource()

        self.assertUnregistered('9876', 'change', 'changepw')

    @defer.inlineCallbacks
    def test_reconfigService_default_changed(self):
        config = mock.Mock()
        config.protocols = {'pb': {'port': '9876'}}
        self.attachChangeSource(pb.PBChangeSource())

        self.startChangeSource()
        yield self.changesource.reconfigServiceWithBuildbotConfig(config)

        self.assertRegistered('9876', 'change', 'changepw')

        config.protocols = {'pb': {'port': '1234'}}

        yield self.changesource.reconfigServiceWithBuildbotConfig(config)

        self.assertUnregistered('9876', 'change', 'changepw')
        self.assertRegistered('1234', 'change', 'changepw')

        yield self.stopChangeSource()

        self.assertUnregistered('1234', 'change', 'changepw')

    @defer.inlineCallbacks
    def test_reconfigService_default_changed_but_inactive(self):
        """reconfig one that's not active on this master"""
        config = mock.Mock()
        config.protocols = {'pb': {'port': '9876'}}
        self.attachChangeSource(pb.PBChangeSource())
        self.setChangeSourceToMaster(self.OTHER_MASTER_ID)

        self.startChangeSource()
        yield self.changesource.reconfigServiceWithBuildbotConfig(config)

        self.assertNotRegistered()

        config.protocols = {'pb': {'port': '1234'}}

        yield self.changesource.reconfigServiceWithBuildbotConfig(config)

        self.assertNotRegistered()

        yield self.stopChangeSource()

        self.assertNotRegistered()
        self.assertNotUnregistered()


class TestChangePerspective(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantDb=True, wantData=True)

    def test_addChange_noprefix(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="bar", files=['a']))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'bar',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [u'a'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_codebase(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="bar", files=[], codebase='cb'))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'bar',
                'branch': None,
                'category': None,
                'codebase': u'cb',
                'comments': None,
                'files': [],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_prefix(self):
        cp = pb.ChangePerspective(self.master, 'xx/')
        d = cp.perspective_addChange(
            dict(who="bar", files=['xx/a', 'yy/b']))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'bar',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [u'a'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_sanitize_None(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(
            dict(project=None, revlink=None, repository=None)
        )

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': None,
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [],
                'project': u'',
                'properties': {},
                'repository': u'',
                'revision': None,
                'revlink': u'',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_when_None(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(
            dict(when=None)
        )

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': None,
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_files_tuple(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(
            dict(files=('a', 'b'))
        )

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': None,
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [u'a', u'b'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_unicode(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(author=u"\N{SNOWMAN}",
                                          comments=u"\N{SNOWMAN}",
                                          files=[u'\N{VERY MUCH GREATER-THAN}']))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'\u2603',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': u'\u2603',
                'files': [u'\u22d9'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_unicode_as_bytestring(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(author=u"\N{SNOWMAN}".encode('utf8'),
                                          comments=u"\N{SNOWMAN}".encode(
                                              'utf8'),
                                          files=[u'\N{VERY MUCH GREATER-THAN}'.encode('utf8')]))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'\u2603',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': u'\u2603',
                'files': [u'\u22d9'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_non_utf8_bytestring(self):
        cp = pb.ChangePerspective(self.master, None)
        bogus_utf8 = b'\xff\xff\xff\xff'
        replacement = bogus_utf8.decode('utf8', 'replace')
        d = cp.perspective_addChange(dict(author=bogus_utf8, files=['a']))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': replacement,
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [u'a'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': None,
            }])
        d.addCallback(check)
        return d

    def test_addChange_old_param_names(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who='me', when=1234,
                                          files=[]))

        def check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'me',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': None,
                'when_timestamp': 1234,
            }])
        d.addCallback(check)
        return d

    def test_createUserObject_git_src(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="c <h@c>", src='git'))

        def check_change(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'c <h@c>',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': None,
                'files': [],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': None,
                'revlink': '',
                'src': u'git',
                'when_timestamp': None,
            }])
        d.addCallback(check_change)
        return d
