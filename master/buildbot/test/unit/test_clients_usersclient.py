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
from twisted.trial import unittest
from twisted.spread import pb
from twisted.internet import defer, reactor
from buildbot.clients import usersclient

class TestUsersClient(unittest.TestCase):

    def setUp(self):
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
        self.conn_host = self.conn_port = None
        self.lostConnection = False

    def _fake_PBClientFactory(self):
        return self.factory

    def _fake_login(self, creds):
        return self.factory.login_d

    def _fake_connectTCP(self, host, port, factory):
        self.conn_host = host
        self.conn_port = port
        self.assertIdentical(factory, self.factory)
        self.factory.login_d.callback(self.remote)

    def _fake_callRemote(self, method, op, ids, info):
        self.assertEqual(method, 'commandline')
        self.called_with = dict(op=op, ids=ids, info=info)
        return defer.succeed(None)

    def _fake_loseConnection(self):
        self.lostConnection = True

    def assertProcess(self, host, port, called_with):
        self.assertEqual([host, port, called_with],
                         [self.conn_host, self.conn_port, self.called_with])

    def test_usersclient_info(self):
        uc = usersclient.UsersClient('localhost', "user", "userpw", 1234)
        d = uc.send('add', None, [{'identifier':'x', 'svn':'x'}])
        def check(_):
            self.assertProcess('localhost', 1234,
                               dict(op='add', ids=None,
                                    info=[dict(identifier='x', svn='x')]))
        d.addCallback(check)
        return d

    def test_usersclient_ids(self):
        uc = usersclient.UsersClient('localhost', "user", "userpw", 1234)
        d = uc.send('remove', ['x'], None)
        def check(_):
            self.assertProcess('localhost', 1234,
                               dict(op='remove', ids=['x'], info=None))
        d.addCallback(check)
        return d
