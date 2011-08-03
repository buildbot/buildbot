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
from buildbot.test.util import changesource, pbmanager, users
from buildbot.util import epoch2datetime

class TestPBChangeSource(
            changesource.ChangeSourceMixin,
            pbmanager.PBManagerMixin,
            unittest.TestCase):

    def setUp(self):
        self.setUpPBChangeSource()
        d = self.setUpChangeSource()
        def setup(_):
            # fill in some extra details of the master
            self.master.slavePortnum = '9999'
            self.master.pbmanager = self.pbmanager
        d.addCallback(setup)

        return d

    def test_registration_slaveport(self):
        return self._test_registration(('9999', 'alice', 'sekrit'),
                user='alice', passwd='sekrit')

    def test_registration_custom_port(self):
        return self._test_registration(('8888', 'alice', 'sekrit'),
                user='alice', passwd='sekrit', port='8888')

    def test_registration_no_userpass(self):
        return self._test_registration(('9999', 'change', 'changepw'))

    def _test_registration(self, exp_registration, **constr_kwargs):
        self.attachChangeSource(pb.PBChangeSource(**constr_kwargs))
        self.startChangeSource()
        self.assertRegistered(*exp_registration)
        d = self.stopChangeSource()
        def check(_):
            self.assertUnregistered(*exp_registration)
        d.addCallback(check)
        return d

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

class TestChangePerspective(users.UsersMixin, unittest.TestCase):
    def setUp(self):
        self.added_changes = []
        self.master = mock.Mock()

        self.setUpUsers()
        self.master.db.users.checkFromGit = self.checkFromGit
        def addChange(**chdict):
            self.src = None
            d = defer.succeed(None)
            def getUid(_):
                uid = None
                if 'src' in chdict:
                    self.src = chdict.pop('src')
                    if self.src:
                        uid = self.createUserObject(chdict['author'], self.src)
                return uid
            d.addCallback(getUid)
            def setChange(uid):
                if self.src:
                    chdict.update({'uid': uid})
                self.added_changes.append(chdict)
                return mock.Mock()
            d.addCallback(setChange)
            return d
        self.master.addChange = addChange

    def test_addChange_noprefix(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="bar", files=['a']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author="bar", files=['a']) ])
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
                    [ dict(project="", revlink="", repository="", files=[]) ])
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
                    links=[u'\N{HEAVY BLACK HEART}'],
                    files=[u'\N{VERY MUCH GREATER-THAN}']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author=u"\N{SNOWMAN}",
                      comments=u"\N{SNOWMAN}",
                      links=[u'\N{HEAVY BLACK HEART}'],
                      files=[u'\N{VERY MUCH GREATER-THAN}']) ])
        d.addCallback(check)
        return d

    def test_addChange_unicode_as_bytestring(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(author=u"\N{SNOWMAN}".encode('utf8'),
                    comments=u"\N{SNOWMAN}".encode('utf8'),
                    links=[u'\N{HEAVY BLACK HEART}'.encode('utf8')],
                    files=[u'\N{VERY MUCH GREATER-THAN}'.encode('utf8')]))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(author=u"\N{SNOWMAN}",
                      comments=u"\N{SNOWMAN}",
                      links=[u'\N{HEAVY BLACK HEART}'],
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

    def test_createUserObject_git_no_match(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="guess"), src='git')
        def check_change(_):
            self.assertEqual(self.added_changes, [ dict(author="guess",
                                                        files=[],
                                                        uid=1) ])
        d.addCallback(check_change)
        def check_users(_):
            self.assertEqual(self.stored_users,
                             [ dict(id=1, uid=1, identifier="guess",
                                    auth_type="full_name",
                                    auth_data="guess") ])
        d.addCallback(check_users)
        return d

    def test_createUserObject_git_match(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="guess"), src='git')
        def check_change(_):
            self.assertEqual(self.added_changes, [ dict(author="guess",
                                                        files=[],
                                                        uid=1) ])
        d.addCallback(check_change)
        def check_users(_):
            self.assertEqual(self.stored_users,
                             [ dict(id=1, uid=1, identifier="guess",
                                    auth_type="full_name",
                                    auth_data="guess") ])
        d.addCallback(check_users)

        d.addCallback(lambda _ : cp.perspective_addChange(
                                     dict(who="guess", files=["yep"]), src='git'))
        def check_change2(_):
            self.assertEqual(self.added_changes[1], dict(author="guess",
                                                         files=["yep"],
                                                         uid=1))
        d.addCallback(check_change2)
        def check_users2(_):
            # should be the same as previously checked
            self.assertEqual(len(self.stored_users), 1)
            self.assertEqual(self.stored_users,
                             [ dict(id=1, uid=1, identifier="guess",
                                    auth_type="full_name",
                                    auth_data="guess") ])
        d.addCallback(check_users2)
        return d

    def test_createUserObject_git_match_email(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="guess <h@c>"), src='git')
        def check_change(_):
            self.assertEqual(self.added_changes, [ dict(author="guess <h@c>",
                                                        files=[],
                                                        uid=1) ])
        d.addCallback(check_change)
        def check_users(_):
            self.assertEqual(len(self.stored_users), 2)
            self.assertEqual(self.stored_users,
                             [ dict(id=1, uid=1, identifier="guess",
                                    auth_type="email",
                                    auth_data="h@c"),
                               dict(id=2, uid=1, identifier="guess",
                                    auth_type="full_name",
                                    auth_data="guess") ])
        d.addCallback(check_users)

        # test if the email is still picked up with the same full_name
        d.addCallback(lambda _ : cp.perspective_addChange(
                                     dict(who="guess", files=["yep"]), src='git'))
        def check_change2(_):
            self.assertEqual(self.added_changes[1], dict(author="guess",
                                                         files=["yep"],
                                                         uid=1))
        d.addCallback(check_change2)
        def check_users2(_):
            # should be the same as previously checked
            self.assertEqual(len(self.stored_users), 2)
            self.assertEqual(self.stored_users,
                             [ dict(id=1, uid=1, identifier="guess",
                                    auth_type="email",
                                    auth_data="h@c"),
                               dict(id=2, uid=1, identifier="guess",
                                    auth_type="full_name",
                                    auth_data="guess") ])
        d.addCallback(check_users2)
        return d
