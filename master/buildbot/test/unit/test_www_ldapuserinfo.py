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
import new
import sys

from twisted.internet import defer
from twisted.trial import unittest

fake_ldap = new.module('ldap')
fake_ldap.SCOPE_SUBTREE = 2
with mock.patch.dict(sys.modules, {'ldap': fake_ldap}):
    from buildbot.www import ldapuserinfo


class FakeLdap(object):

    def __init__(self):
        def simple_bind_s(who, cred):
            pass
        self.simple_bind_s = mock.Mock(spec=simple_bind_s)

        def search_s(base, scope, filterstr='f', attrlist=None, attrsonly=0):
            pass
        self.search_s = mock.Mock(spec=search_s)


class LdapUserInfo(unittest.TestCase):
    # we completetly fake the python-ldap module, so no need to require
    # it to run the unit tests

    def setUp(self):
        self.ldap = FakeLdap()
        fake_ldap.initialize = lambda uri: self.ldap

        self.userInfoProvider = ldapuserinfo.LdapUserInfo(
            uri="ldap://uri", bindUser="user", bindPw="pass",
            accountBase="accbase", groupBase="groupbase",
            accountPattern="accpattern", groupMemberPattern="groupMemberPattern",
            accountFullName="accountFullName",
            accountEmail="accountEmail",
            groupName="groupName",
            avatarPattern="avatar",
            avatarData="picture",
            accountExtraFields=["myfield"])

    @defer.inlineCallbacks
    def test_updateUserInfoNoResults(self):
        self.ldap.search_s.side_effect = [[], [], []]
        try:
            yield self.userInfoProvider.getUserInfo("me")
        except KeyError, e:
            self.assertEqual(
                repr(e), "KeyError('ldap search \"accpattern\" returned 0 results',)")
        else:
            self.fail("should have raised a key error")

    @defer.inlineCallbacks
    def test_updateUserInfoNoGroups(self):
        self.ldap.search_s.side_effect = [[(
            "cn", {"accountFullName": ["me too"],
                   "accountEmail": ["mee@too"]})], [], []]
        res = yield self.userInfoProvider.getUserInfo("me")
        self.assertEqual(self.ldap.search_s.call_args_list, [
            (('accbase', 2, 'accpattern',
             ['accountEmail', 'accountFullName', 'dn', 'myfield']), {}),
            (('groupbase', 2, 'groupMemberPattern', ['groupName']), {}),
        ])
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': [], 'username': 'me'})

    @defer.inlineCallbacks
    def test_updateUserInfoGroups(self):
        self.ldap.search_s = mock.Mock(side_effect=
                                       [[("cn", {"accountFullName": ["me too"],
                                                 "accountEmail": ["mee@too"]})],
                                        [("cn", {"groupName": ["group"]}),
                                         ("cn", {"groupName": ["group2"]})
                                         ], []])
        res = yield self.userInfoProvider.getUserInfo("me")
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': ["group", "group2"], 'username': 'me'})

    @defer.inlineCallbacks
    def test_getUserAvatar(self):
        self.ldap.search_s.side_effect = [
            [("cn", {"picture": ["\x89PNG lljklj"]})]]
        res = yield self.userInfoProvider.getUserAvatar("me", 21, None)
        self.assertEqual(self.ldap.search_s.call_args_list, [
            (('accbase', 2, 'avatar', ['picture']), {}),
        ])
        self.assertEqual(res, ('image/png', '\x89PNG lljklj'))
