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
from buildbot.test.util import users
from buildbot.clients import usersclient

class TestUsersClient(unittest.TestCase, users.UsersMixin):

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

        # set up for perspective_commandline calls
        self.setUpUsers()

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
        results = self.perspective_commandline(op, ids, info)
        return defer.succeed(results)

    def _fake_loseConnection(self):
        self.lostConnection = True

    def assertProcess(self, host, port, stored_users):
        self.assertEqual([host, port, stored_users],
                         [self.conn_host, self.conn_port, self.stored_users])

    def test_user_add(self):
        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('add', None, [{'identifier':'x', 'a':'b'}])
        def check(res):
            self.assertProcess('localhost', 1234,
                               [{'a': 'b', 'identifier': 'x', 'uid': 1}])
        d.addCallback(check)
        return d

    def test_user_update(self):
        self.stored_users.append({'identifier':'x', 'a':'c', 'uid': 1})
        self.next_id += self.next_id

        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('update', None, [{'identifier':'x', 'a':'b'}])
        def check(res):
            self.assertProcess('localhost', 1234,
                               [{'identifier':'x', 'a':'b', 'uid': 1}])
        d.addCallback(check)
        return d

    def test_user_update_no_match(self):
        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('update', None, [{'identifier':'x', 'a':'b'}])
        def check(res):
            self.assertProcess('localhost', 1234, [])
        d.addCallback(check)
        return d

    def test_user_remove(self):
        self.stored_users.append({'identifier':'x', 'a':'c', 'uid': 1})
        self.next_id += self.next_id

        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('remove', ['x'], None)
        def check(res):
            self.assertProcess('localhost', 1234, [])
        d.addCallback(check)
        return d

    def test_user_remove_no_match(self):
        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('remove', ['x'], None)
        def check(res):
            self.assertProcess('localhost', 1234, [])
        d.addCallback(check)
        return d

    def test_user_show(self):
        self.stored_users.append({'identifier':'x', 'a':'c', 'uid': 1})
        self.next_id += self.next_id

        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('show', ['x'], None)
        def check(res):
            self.assertProcess('localhost', 1234,
                               [{'identifier':'x', 'a':'c', 'uid': 1}])
        d.addCallback(check)
        return d

    def test_user_show_no_match(self):
        uc = usersclient.UsersClient('localhost:1234')
        d = uc.send('show', ['x'], None)
        def check(res):
            self.assertProcess('localhost', 1234, [])
        d.addCallback(check)
        return d
