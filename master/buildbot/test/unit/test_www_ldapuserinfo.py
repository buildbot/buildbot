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

fake_ldap = new.module('ldap3')
fake_ldap.SEARCH_SCOPE_WHOLE_SUBTREE = 2
with mock.patch.dict(sys.modules, {'ldap3': fake_ldap}):
    from buildbot.www import ldapuserinfo


class FakeLdap(object):

    def __init__(self):
        def search(base, filterstr='f', scope=None, attributes=None):
            pass
        self.search = mock.Mock(spec=search)


class LdapUserInfo(unittest.TestCase):
    # we completetly fake the python3-ldap module, so no need to require
    # it to run the unit tests

    def setUp(self):
        self.ldap = FakeLdap()

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
        self.userInfoProvider.connectLdap = lambda: self.ldap

        def search(base, filterstr='f', attributes=None):
            pass
        self.userInfoProvider.search = mock.Mock(spec=search)

    def makeSearchSideEffect(self, l):
        l = [[{'dn': i[0], 'raw_attributes': i[1]} for i in r]
             for r in l]
        self.userInfoProvider.search.side_effect = l

    def assertSearchCalledWith(self, exp):
        got = self.userInfoProvider.search.call_args_list
        self.assertEqual(len(exp), len(got))
        for i in xrange(len(exp)):
            self.assertEqual(exp[i][0][0], got[i][0][1])
            self.assertEqual(exp[i][0][1], got[i][0][2])
            self.assertEqual(exp[i][0][2], got[i][1]['attributes'])

    @defer.inlineCallbacks
    def test_updateUserInfoNoResults(self):
        self.makeSearchSideEffect([[], [], []])
        try:
            yield self.userInfoProvider.getUserInfo("me")
        except KeyError as e:
            self.assertEqual(
                repr(e), "KeyError('ldap search \"accpattern\" returned 0 results',)")
        else:
            self.fail("should have raised a key error")

    @defer.inlineCallbacks
    def test_updateUserInfoNoGroups(self):
        self.makeSearchSideEffect([[(
            "cn", {"accountFullName": "me too",
                   "accountEmail": "mee@too"})], [], []])
        res = yield self.userInfoProvider.getUserInfo("me")
        self.assertSearchCalledWith([
            (('accbase', 'accpattern',
              ['accountEmail', 'accountFullName', 'dn', 'myfield']), {}),
            (('groupbase', 'groupMemberPattern', ['groupName']), {}),
        ])
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': [], 'username': 'me'})

    @defer.inlineCallbacks
    def test_updateUserInfoGroups(self):
        self.makeSearchSideEffect([[("cn", {"accountFullName": "me too",
                                  "accountEmail": "mee@too"})],
                         [("cn", {"groupName": ["group"]}),
                          ("cn", {"groupName": ["group2"]})
                          ], []])
        res = yield self.userInfoProvider.getUserInfo("me")
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': ["group", "group2"], 'username': 'me'})

    @defer.inlineCallbacks
    def test_getUserAvatar(self):
        self.makeSearchSideEffect([
            [("cn", {"picture": ["\x89PNG lljklj"]})]])
        res = yield self.userInfoProvider.getUserAvatar("me", 21, None)
        self.assertSearchCalledWith([
            (('accbase', 'avatar', ['picture']), {}),
        ])
        self.assertEqual(res, ('image/png', '\x89PNG lljklj'))
