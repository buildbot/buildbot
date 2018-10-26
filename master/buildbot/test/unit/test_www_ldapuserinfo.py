# coding: utf-8
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
from __future__ import print_function
from future.builtins import range

import sys
import types

import mock

from twisted.internet import defer
from twisted.trial import unittest


def get_config_parameter(p):
    params = {'DEFAULT_SERVER_ENCODING': 'utf-8'}
    return params[p]


fake_ldap = types.ModuleType('ldap3')
fake_ldap.SEARCH_SCOPE_WHOLE_SUBTREE = 2
fake_ldap.get_config_parameter = get_config_parameter

with mock.patch.dict(sys.modules, {'ldap3': fake_ldap}):
    from buildbot.www import ldapuserinfo


class FakeLdap(object):

    def __init__(self):
        def search(base, filterstr='f', scope=None, attributes=None):
            pass
        self.search = mock.Mock(spec=search)


class CommonTestCase(unittest.TestCase):

    """Common fixture for all ldapuserinfo tests

    we completely fake the ldap3 module, so no need to require
    it to run the unit tests
    """

    def setUp(self):
        self.ldap = FakeLdap()
        self.makeUserInfoProvider()
        self.userInfoProvider.connectLdap = lambda: self.ldap

        def search(base, filterstr='f', attributes=None):
            pass
        self.userInfoProvider.search = mock.Mock(spec=search)

    def makeUserInfoProvider(self):
        """To be implemented by subclasses"""
        raise NotImplementedError

    def _makeSearchSideEffect(self, attribute_type, ret):
        ret = [[{'dn': i[0], attribute_type: i[1]} for i in r]
             for r in ret]
        self.userInfoProvider.search.side_effect = ret

    def makeSearchSideEffect(self, ret):
        return self._makeSearchSideEffect('attributes', ret)

    def makeRawSearchSideEffect(self, ret):
        return self._makeSearchSideEffect('raw_attributes', ret)

    def assertSearchCalledWith(self, exp):
        got = self.userInfoProvider.search.call_args_list
        self.assertEqual(len(exp), len(got))
        for i in range(len(exp)):
            self.assertEqual(exp[i][0][0], got[i][0][1])
            self.assertEqual(exp[i][0][1], got[i][0][2])
            self.assertEqual(exp[i][0][2], got[i][1]['attributes'])


class LdapUserInfo(CommonTestCase):

    def makeUserInfoProvider(self):
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
        self.makeSearchSideEffect([[], [], []])
        try:
            yield self.userInfoProvider.getUserInfo("me")
        except KeyError as e:
            self.assertRegex(
                repr(e), r"KeyError\('ldap search \"accpattern\" returned 0 results',?\)")
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
              ['accountEmail', 'accountFullName', 'myfield']), {}),
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
    def test_updateUserInfoGroupsUnicodeDn(self):
        # In case of non Ascii DN, ldap3 lib returns an UTF-8 str
        dn = u"cn=Sébastien,dc=example,dc=org"
        # If groupMemberPattern is an str, and dn is not decoded,
        # the resulting filter will be an str, leading to UnicodeDecodeError
        # in ldap3.protocol.convert.validate_assertion_value()
        # So we use an unicode pattern:
        self.userInfoProvider.groupMemberPattern = u'(member=%(dn)s)'
        self.makeSearchSideEffect([[(dn, {"accountFullName": "me too",
                                          "accountEmail": "mee@too"})],
                                   [("cn", {"groupName": ["group"]}),
                                    ("cn", {"groupName": ["group2"]})
                                    ], []])
        res = yield self.userInfoProvider.getUserInfo("me")
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': ["group", "group2"], 'username': 'me'})

    @defer.inlineCallbacks
    def _getUserAvatar(self, mimeTypeAndData):
        (mimeType, data) = mimeTypeAndData
        self.makeRawSearchSideEffect([
            [("cn", {"picture": [data]})]])
        res = yield self.userInfoProvider.getUserAvatar("me", 21, None)
        self.assertSearchCalledWith([
            (('accbase', 'avatar', ['picture']), {}),
        ])
        defer.returnValue(res)

    @defer.inlineCallbacks
    def test_getUserAvatarPNG(self):
        mimeTypeAndData = ('image/png', b'\x89PNG lljklj')
        res = yield self._getUserAvatar(mimeTypeAndData)
        self.assertEqual(res, mimeTypeAndData)

    @defer.inlineCallbacks
    def test_getUserAvatarJPEG(self):
        mimeTypeAndData = ('image/jpeg', b'\xff\xd8\xff lljklj')
        res = yield self._getUserAvatar(mimeTypeAndData)
        self.assertEqual(res, mimeTypeAndData)

    @defer.inlineCallbacks
    def test_getUserAvatarGIF(self):
        mimeTypeAndData = ('image/gif', b'GIF8 lljklj')
        res = yield self._getUserAvatar(mimeTypeAndData)
        self.assertEqual(res, mimeTypeAndData)

    @defer.inlineCallbacks
    def test_getUserAvatarUnknownType(self):
        mimeTypeAndData = ('', b'unknown image format')
        res = yield self._getUserAvatar(mimeTypeAndData)
        self.assertIsNone(res)


class LdapUserInfoNoGroups(CommonTestCase):

    def makeUserInfoProvider(self):
        self.userInfoProvider = ldapuserinfo.LdapUserInfo(
            uri="ldap://uri", bindUser="user", bindPw="pass",
            accountBase="accbase",
            accountPattern="accpattern",
            accountFullName="accountFullName",
            accountEmail="accountEmail",
            avatarPattern="avatar",
            avatarData="picture",
            accountExtraFields=["myfield"])

    @defer.inlineCallbacks
    def test_updateUserInfo(self):
        self.makeSearchSideEffect([[(
            "cn", {"accountFullName": "me too",
                   "accountEmail": "mee@too"})], [], []])
        res = yield self.userInfoProvider.getUserInfo("me")
        self.assertSearchCalledWith([
            (('accbase', 'accpattern',
              ['accountEmail', 'accountFullName', 'myfield']), {}),
        ])
        self.assertEqual(res, {'email': 'mee@too', 'full_name': 'me too',
                               'groups': [], 'username': 'me'})


class Config(unittest.TestCase):

    def test_missing_group_name(self):
        self.assertRaises(ValueError,
                          ldapuserinfo.LdapUserInfo,
                          groupMemberPattern="member=%(dn)s",
                          groupBase="grpbase",
                          uri="ldap://uri", bindUser="user", bindPw="pass",
                          accountBase="accbase",
                          accountPattern="accpattern",
                          accountFullName="accountFullName",
                          accountEmail="accountEmail")

    def test_missing_group_base(self):
        self.assertRaises(ValueError,
                          ldapuserinfo.LdapUserInfo,
                          groupMemberPattern="member=%(dn)s",
                          groupName="group",
                          uri="ldap://uri", bindUser="user", bindPw="pass",
                          accountBase="accbase",
                          accountPattern="accpattern",
                          accountFullName="accountFullName",
                          accountEmail="accountEmail")

    def test_missing_two_params(self):
        self.assertRaises(ValueError,
                          ldapuserinfo.LdapUserInfo,
                          groupName="group",
                          uri="ldap://uri", bindUser="user", bindPw="pass",
                          accountBase="accbase",
                          accountPattern="accpattern",
                          accountFullName="accountFullName",
                          accountEmail="accountEmail")
