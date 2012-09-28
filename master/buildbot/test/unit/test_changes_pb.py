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


"""
Test the PB change source.
"""

import mock
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.changes import pb
from buildbot.test.util import changesource, pbmanager
from buildbot.util import epoch2datetime

class TestPBChangeSource(
            changesource.ChangeSourceMixin,
            pbmanager.PBManagerMixin,
            unittest.TestCase):

    def setUp(self):
        self.setUpPBChangeSource()
        d = self.setUpChangeSource()
        @d.addCallback
        def setup(_):
            self.master.pbmanager = self.pbmanager

        return d

    def test_registration_no_slaveport(self):
        return self._test_registration(None,
                user='alice', passwd='sekrit')

    def test_registration_global_slaveport(self):
        return self._test_registration(('9999', 'alice', 'sekrit'),
                slavePort='9999', user='alice', passwd='sekrit')

    def test_registration_custom_port(self):
        return self._test_registration(('8888', 'alice', 'sekrit'),
                user='alice', passwd='sekrit', port='8888')

    def test_registration_no_userpass(self):
        return self._test_registration(('9939', 'change', 'changepw'),
                slavePort='9939')

    def test_registration_no_userpass_no_global(self):
        return self._test_registration(None)

    @defer.inlineCallbacks
    def _test_registration(self, exp_registration, slavePort=None,
                        **constr_kwargs):
        config = mock.Mock()
        config.slavePortnum = slavePort
        self.attachChangeSource(pb.PBChangeSource(**constr_kwargs))

        self.startChangeSource()
        yield self.changesource.reconfigService(config)

        if exp_registration:
            self.assertRegistered(*exp_registration)
        else:
            self.assertNotRegistered()

        yield self.stopChangeSource()

        if exp_registration:
            self.assertUnregistered(*exp_registration)

    def test_perspective(self):
        self.attachChangeSource(pb.PBChangeSource('alice', 'sekrit', port='8888'))
        persp = self.changesource.getPerspective(mock.Mock(), 'alice')
        self.assertIsInstance(persp, pb.ChangePerspective)

    def test_describe(self):
        cs = pb.PBChangeSource()
        self.assertSubstring("PBChangeSource", cs.describe())

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
        yield self.changesource.reconfigService(config)

        self.assertRegistered('9876', 'change', 'changepw')

        yield self.stopChangeSource()

        self.assertUnregistered('9876', 'change', 'changepw')

    @defer.inlineCallbacks
    def test_reconfigService_default_changed(self):
        config = mock.Mock()
        config.slavePortnum = '9876'
        self.attachChangeSource(pb.PBChangeSource())

        self.startChangeSource()
        yield self.changesource.reconfigService(config)

        self.assertRegistered('9876', 'change', 'changepw')

        config.slavePortnum = '1234'

        yield self.changesource.reconfigService(config)

        self.assertUnregistered('9876', 'change', 'changepw')
        self.assertRegistered('1234', 'change', 'changepw')

        yield self.stopChangeSource()

        self.assertUnregistered('1234', 'change', 'changepw')


class TestChangePerspective(unittest.TestCase):
    def setUp(self):
        self.added_changes = []
        self.master = mock.Mock()

        def addChange(**chdict):
            self.added_changes.append(chdict)
            return defer.succeed(mock.Mock())
        self.master.addChange = addChange

    def test_addChange_noprefix(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="bar", files=['a']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author="bar", files=['a']) ])
        d.addCallback(check)
        return d

    def test_addChange_codebase(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="bar", files=[], codebase='cb'))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author="bar", files=[], codebase='cb') ])
        d.addCallback(check)
        return d

    def test_addChange_prefix(self):
        cp = pb.ChangePerspective(self.master, 'xx/')
        d = cp.perspective_addChange(
                dict(who="bar", files=['xx/a', 'yy/b']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author="bar", files=['a']) ])
        d.addCallback(check)
        return d

    def test_addChange_sanitize_None(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(
                dict(project=None, revlink=None, repository=None)
                )
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(project="", revlink="", repository="",
                           files=[]) ])
        d.addCallback(check)
        return d

    def test_addChange_when_None(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(
                dict(when=None)
                )
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(when_timestamp=None, files=[]) ])
        d.addCallback(check)
        return d

    def test_addChange_files_tuple(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(
                dict(files=('a', 'b'))
                )
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(files=['a', 'b']) ])
        d.addCallback(check)
        return d

    def test_addChange_unicode(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(author=u"\N{SNOWMAN}",
                    comments=u"\N{SNOWMAN}",
                    files=[u'\N{VERY MUCH GREATER-THAN}']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author=u"\N{SNOWMAN}",
                      comments=u"\N{SNOWMAN}",
                      files=[u'\N{VERY MUCH GREATER-THAN}']) ])
        d.addCallback(check)
        return d

    def test_addChange_unicode_as_bytestring(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(author=u"\N{SNOWMAN}".encode('utf8'),
                    comments=u"\N{SNOWMAN}".encode('utf8'),
                    files=[u'\N{VERY MUCH GREATER-THAN}'.encode('utf8')]))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author=u"\N{SNOWMAN}",
                      comments=u"\N{SNOWMAN}",
                      files=[u'\N{VERY MUCH GREATER-THAN}']) ])
        d.addCallback(check)
        return d

    def test_addChange_non_utf8_bytestring(self):
        cp = pb.ChangePerspective(self.master, None)
        bogus_utf8 = '\xff\xff\xff\xff'
        replacement = bogus_utf8.decode('utf8', 'replace')
        d = cp.perspective_addChange(dict(author=bogus_utf8, files=['a']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author=replacement, files=['a']) ])
        d.addCallback(check)
        return d

    def test_addChange_old_param_names(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(isdir=1, who='me', when=1234,
                                          files=[]))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(is_dir=1, author='me', files=[],
                        when_timestamp=epoch2datetime(1234)) ])
        d.addCallback(check)
        return d

    def test_createUserObject_git_src(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="c <h@c>", src='git'))
        def check_change(_):
            self.assertEqual(self.added_changes, [ dict(author="c <h@c>",
                                                        files=[],
                                                        src='git') ])
        d.addCallback(check_change)
        return d
