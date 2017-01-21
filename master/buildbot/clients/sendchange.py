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

from twisted.cred import credentials
from twisted.internet import reactor
from twisted.spread import pb


class Sender:

    def __init__(self, master, auth=('change', 'changepw'), encoding='utf8'):
        self.username, self.password = auth
        self.host, self.port = master.split(":")
        self.port = int(self.port)
        self.encoding = encoding

    def send(self, branch, revision, comments, files, who=None, category=None,
             when=None, properties=None, repository='', vc=None, project='',
             revlink='', codebase=None):
        if properties is None:
            properties = {}

        change = {'project': project, 'repository': repository, 'who': who,
                  'files': files, 'comments': comments, 'branch': branch,
                  'revision': revision, 'category': category, 'when': when,
                  'properties': properties, 'revlink': revlink, 'src': vc}

        # codebase is only sent if set; this won't work with masters older than
        # 0.8.7
        if codebase:
            change['codebase'] = codebase

        for key in change:
            if isinstance(change[key], bytes):
                change[key] = change[key].decode(self.encoding, 'replace')
        change['files'] = list(change['files'])
        for i, file in enumerate(change.get('files', [])):
            if isinstance(file, bytes):
                change['files'][i] = file.decode(self.encoding, 'replace')

        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword(self.username, self.password))
        reactor.connectTCP(self.host, self.port, f)

        @d.addCallback
        def call_addChange(remote):
            d = remote.callRemote('addChange', change)
            d.addCallback(lambda res: remote.broker.transport.loseConnection())
            return d

        return d
