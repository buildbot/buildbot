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

import mock
import sys

from twisted.internet import defer
from twisted.trial import unittest


class FakeLdap(object):
    initialize = mock.Mock()
    simple_bind_s = mock.Mock()
    search_s = mock.Mock()
    SCOPE_SUBTREE = 2


class LdapUserInfos(unittest.TestCase):
    # we completetly fake the python-ldap module, so no need to require
    # it to run the unit tests
    def setUp(self):
        self.oldldap = sys.modules.get("ldap", None)
        self.ldap = FakeLdap()
        sys.modules["ldap"] = self.ldap
        from buildbot.www import ldapuserinfos

        self.userinfos = ldapuserinfos.LdapUserInfos(
            uri="ldap://uri", bind_user="user", bind_pw="pass",
            accountBase="accbase", groupBase="groupbase",
            accountPattern="accpattern", groupMemberPattern="groupMemberPattern",
            accountFullName="accountFullName",
            accountEmail="accountEmail",
            groupName="groupName",
            avatarPattern="avatar",
            avatarData="picture",
            accountExtraFields=["myfield"])
        self.ldap.initialize = mock.Mock(side_effect=[self.ldap])
        self.userinfos.getLdap = lambda: self.ldap

    def tearDown(self):
        if self.oldldap is None:
            del sys.modules["ldap"]
        else:
            sys.modules["ldap"] = self.oldldap

    @defer.inlineCallbacks
    def test_updateUserInfosNoResults(self):
        self.ldap.search_s = mock.Mock(side_effect=
                                       [[], [], []])
        try:
            yield self.userinfos.getUserInfos("me")
        except KeyError, e:
            self.assertEqual(repr(e), "KeyError('ldap search \"accpattern\" returned 0 results',)")
        else:
            self.fail("should have raised a key error")

    @defer.inlineCallbacks
    def test_updateUserInfosNoGroups(self):
        self.ldap.search_s = mock.Mock(side_effect=
                                       [[("cn", {"accountFullName": ["me too"],
                                                 "accountEmail": ["mee@too"]})], [], []])
        res = yield self.userinfos.getUserInfos("me")
        self.assertEqual(self.ldap.search_s.call_args_list, [
            (('accbase', 2, 'accpattern', ['accountEmail', 'accountFullName', 'dn', 'myfield']), {}),
            (('groupbase', 2, 'groupMemberPattern', ['groupName']), {}),
        ])
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': [], 'username': 'me'})

    @defer.inlineCallbacks
    def test_updateUserInfosGroups(self):
        self.ldap.search_s = mock.Mock(side_effect=
                                       [[("cn", {"accountFullName": ["me too"],
                                                 "accountEmail": ["mee@too"]})],
                                        [("cn", {"groupName": ["group"]}),
                                         ("cn", {"groupName": ["group2"]})
                                         ], []])
        res = yield self.userinfos.getUserInfos("me")
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': ["group", "group2"], 'username': 'me'})

    @defer.inlineCallbacks
    def test_getUserAvatar(self):
        self.ldap.search_s = mock.Mock(side_effect=
                                       [[("cn", {"picture": ["\x89PNG lljklj"]})],
                                        ])
        res = yield self.userinfos.getUserAvatar("me", 21, None)
        self.assertEqual(self.ldap.search_s.call_args_list, [
            (('accbase', 2, 'avatar', ['picture']), {}),
        ])
        self.assertEqual(res, ('image/png', '\x89PNG lljklj'))
