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
from twisted.internet import defer, reactor
from twisted.spread import pb

class PBClientMixin(object):

    def setUpPBClient(self):
        # patch out some PB components and make up some mocks
        self.patch(pb, 'PBClientFactory', self._fake_PBClientFactory)
        self.patch(reactor, 'connectTCP', self._fake_connectTCP)

        self.factory = mock.Mock(name='PBClientFactory')
        self.factory.login = self._fake_login
        self.factory.login_d = defer.Deferred()

        self.remote = mock.Mock(name='PB Remote')
        self.remote.callRemote = self._fake_callRemote
        self.remote.broker.transport.loseConnection = self._fake_loseConnection

        # results
        self.creds = None
        self.conn_host = self.conn_port = None
        self.lostConnection = False

    def _fake_PBClientFactory(self):
        return self.factory

    def _fake_login(self, creds):
        self.creds = creds
        return self.factory.login_d

    def _fake_connectTCP(self, host, port, factory):
        self.conn_host = host
        self.conn_port = port
        self.assertIdentical(factory, self.factory)
        self.factory.login_d.callback(self.remote)

    def _fake_callRemote(self, method, change):
        raise NotImplementedError()

    def _fake_loseConnection(self):
        self.lostConnection = True
