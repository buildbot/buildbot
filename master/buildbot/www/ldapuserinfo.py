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


# NOTE regarding LDAP encodings:
#
# By default the encoding used in ldap3 is utf-8. The encoding is user-configurable, though.
# For more information check ldap3's documentation on this topic:
# http://ldap3.readthedocs.io/encoding.html
#
# It is recommended to use ldap3's auto-decoded `attributes` values for
# `unicode` and `raw_*` attributes for `bytes`.


from urllib.parse import urlparse

import ldap3

from twisted.internet import threads

from buildbot.util import bytes2unicode
from buildbot.util import flatten
from buildbot.www import auth
from buildbot.www import avatar


class LdapUserInfo(avatar.AvatarBase, auth.UserInfoProviderBase):
    name = 'ldap'

    def __init__(self, uri, bindUser, bindPw,
                 accountBase,
                 accountPattern,
                 accountFullName,
                 accountEmail,
                 groupBase=None,
                 groupMemberPattern=None,
                 groupName=None,
                 avatarPattern=None,
                 avatarData=None,
                 accountExtraFields=None):
        self.uri = uri
        self.bindUser = bindUser
        self.bindPw = bindPw
        self.accountBase = accountBase
        self.accountEmail = accountEmail
        self.accountPattern = accountPattern
        self.accountFullName = accountFullName
        group_params = [p for p in (groupName, groupMemberPattern, groupBase)
                        if p is not None]
        if len(group_params) not in (0, 3):
            raise ValueError(
                "Incomplete LDAP groups configuration. "
                "To use Ldap groups, you need to specify the three "
                "parameters (groupName, groupMemberPattern and groupBase). ")

        self.groupName = groupName
        self.groupMemberPattern = groupMemberPattern
        self.groupBase = groupBase
        self.avatarPattern = avatarPattern
        self.avatarData = avatarData
        if accountExtraFields is None:
            accountExtraFields = []
        self.accountExtraFields = accountExtraFields
        self.ldap_encoding = ldap3.get_config_parameter('DEFAULT_SERVER_ENCODING')

    def connectLdap(self):
        server = urlparse(self.uri)
        netloc = server.netloc.split(":")
        # define the server and the connection
        s = ldap3.Server(netloc[0], port=int(netloc[1]), use_ssl=server.scheme == 'ldaps',
                         get_info=ldap3.ALL)

        auth = ldap3.SIMPLE
        if self.bindUser is None and self.bindPw is None:
            auth = ldap3.ANONYMOUS

        c = ldap3.Connection(s, auto_bind=True, client_strategy=ldap3.SYNC,
                             user=self.bindUser, password=self.bindPw,
                             authentication=auth)
        return c

    def search(self, c, base, filterstr='f', attributes=None):
        c.search(base, filterstr, ldap3.SUBTREE, attributes=attributes)
        return c.response

    def getUserInfo(self, username):
        username = bytes2unicode(username)

        def thd():
            c = self.connectLdap()
            infos = {'username': username}
            pattern = self.accountPattern % dict(username=username)
            res = self.search(c, self.accountBase, pattern,
                              attributes=[
                                  self.accountEmail, self.accountFullName] +
                              self.accountExtraFields)
            if len(res) != 1:
                raise KeyError("ldap search \"{}\" returned {} results".format(pattern, len(res)))
            dn, ldap_infos = res[0]['dn'], res[0]['attributes']

            def getFirstLdapInfo(x):
                if isinstance(x, list):
                    x = x[0] if x else None
                return x

            infos['full_name'] = getFirstLdapInfo(ldap_infos[self.accountFullName])
            infos['email'] = getFirstLdapInfo(ldap_infos[self.accountEmail])
            for f in self.accountExtraFields:
                if f in ldap_infos:
                    infos[f] = getFirstLdapInfo(ldap_infos[f])

            if self.groupMemberPattern is None:
                infos['groups'] = []
                return infos

            # needs double quoting of backslashing
            pattern = self.groupMemberPattern % dict(dn=dn)
            res = self.search(c, self.groupBase, pattern,
                              attributes=[self.groupName])
            infos['groups'] = flatten([group_infos['attributes'][self.groupName]
                                      for group_infos in res])

            return infos
        return threads.deferToThread(thd)

    def findAvatarMime(self, data):
        # http://en.wikipedia.org/wiki/List_of_file_signatures
        if data.startswith(b"\xff\xd8\xff"):
            return ("image/jpeg", data)
        if data.startswith(b"\x89PNG"):
            return ("image/png", data)
        if data.startswith(b"GIF8"):
            return ("image/gif", data)
        # ignore unknown image format
        return None

    def getUserAvatar(self, user_email, size, defaultAvatarUrl):
        user_email = bytes2unicode(user_email)

        def thd():
            c = self.connectLdap()
            pattern = self.avatarPattern % dict(email=user_email)
            res = self.search(c, self.accountBase, pattern,
                              attributes=[self.avatarData])
            if not res:
                return None
            ldap_infos = res[0]['raw_attributes']
            if self.avatarData in ldap_infos and ldap_infos[self.avatarData]:
                data = ldap_infos[self.avatarData][0]
                return self.findAvatarMime(data)
            return None
        return threads.deferToThread(thd)
