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

import ldap

from buildbot.util import flatten
from buildbot.www import auth
from buildbot.www import avatar
from twisted.internet import threads


class LdapUserInfo(avatar.AvatarBase, auth.UserInfoProviderBase):
    name = 'ldap'

    def __init__(self, uri, bindUser, bindPw,
                 accountBase, groupBase,
                 accountPattern, groupMemberPattern,
                 accountFullName,
                 accountEmail,
                 groupName,
                 avatarPattern=None,
                 avatarData=None,
                 accountExtraFields=[]):
        avatar.AvatarBase.__init__(self)
        auth.UserInfoProviderBase.__init__(self)
        self.uri = uri
        self.bindUser = bindUser
        self.bindPw = bindPw
        self.accountBase = accountBase
        self.accountEmail = accountEmail
        self.accountPattern = accountPattern
        self.accountFullName = accountFullName
        self.groupName = groupName
        self.groupMemberPattern = groupMemberPattern
        self.groupBase = groupBase
        self.avatarPattern = avatarPattern
        self.avatarData = avatarData
        self.accountExtraFields = accountExtraFields

    def getUserInfo(self, username):
        def thd():
            infos = {'username': username}
            l = ldap.initialize(self.uri)
            l.simple_bind_s(self.bindUser, self.bindPw)
            pattern = self.accountPattern % dict(username=username)
            res = l.search_s(self.accountBase, ldap.SCOPE_SUBTREE, pattern, [
                self.accountEmail, self.accountFullName, 'dn'] + self.accountExtraFields)
            if len(res) != 1:
                raise KeyError("ldap search \"%s\" returned %d results" % (pattern, len(res)))
            dn, ldap_infos = res[0]
            infos['full_name'] = ldap_infos[self.accountFullName][0]
            infos['email'] = ldap_infos[self.accountEmail][0]
            for f in self.accountExtraFields:
                if f in ldap_infos:
                    infos[f] = ldap_infos[f][0]
            # needs double quoting of backslashing
            pattern = self.groupMemberPattern % dict(dn=dn.replace('\\', '\\\\'))
            res = l.search_s(self.groupBase, ldap.SCOPE_SUBTREE, pattern, [
                self.groupName])
            infos['groups'] = flatten([group_infos[self.groupName] for gdn, group_infos in res])
            return infos
        return threads.deferToThread(thd)

    def findAvatarMime(self, data):
        # http://en.wikipedia.org/wiki/List_of_file_signatures
        if data.startswith("\xff\xd8\xff"):
            return ("image/jpeg", data)
        if data.startswith("\x89PNG"):
            return ("image/png", data)
        if data.startswith("GIF8"):
            return ("image/gif", data)
        # ignore unknown image format
        return None

    def getUserAvatar(self, user_email, size, defaultAvatarUrl):
        def thd():
            l = ldap.initialize(self.uri)
            l.simple_bind_s(self.bindUser, self.bindPw)
            pattern = self.avatarPattern % dict(email=user_email)
            res = l.search_s(self.accountBase, ldap.SCOPE_SUBTREE, pattern, [self.avatarData])
            if len(res) == 0:
                return None
            dn, ldap_infos = res[0]
            if self.avatarData in ldap_infos and len(ldap_infos[self.avatarData]) > 0:
                data = ldap_infos[self.avatarData][0]
                return self.findAvatarMime(data)
            return None
        return threads.deferToThread(thd)
