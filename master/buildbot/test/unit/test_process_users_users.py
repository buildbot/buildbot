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

import mock, os
from twisted.trial import unittest
from twisted.internet import defer

from buildbot.process.users import users
from buildbot.db import users as db_users

from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class UsersTests(connector_component.ConnectorComponentMixin,
                 unittest.TestCase):

    # both passwords are 'marla'
    htpasswd_temp = "tyler:GamXGImzG7bNQ\nnarrator:fPpd/KoR2HCts"

    def setUp(self):
        d = self.setUpConnectorComponent(table_names=['users'])
        def htpasswd_file(_):
            self.htfile = open(".htpasswd_temp", "w+")
            self.htfile.write(self.htpasswd_temp)
            self.htfile.close()
        d.addCallback(htpasswd_file)
        def finish_setup(_):
            self.master = mock.Mock()
            self.db.users = db_users.UsersConnectorComponent(self.db)
            self.master.db.users = self.db.users
        d.addCallback(finish_setup)
        return d

    def tearDown(self):
        os.remove(self.htfile.name)
        return self.tearDownConnectorComponent()

    def test_createUserObject_no_vc(self):
        d = users.createUserObject(self.master, "Tyler Durden", None)
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 0)
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_git_with_email(self):
        d = users.createUserObject(self.master,
                                   "Tyler Durden <tyler@mayhem.net>", 'git')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'Tyler Durden')
                self.assertEqual(rows[0].auth_type, 'email')
                self.assertEqual(rows[0].auth_data, 'tyler@mayhem.net')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'Tyler Durden')
                self.assertEqual(rows[1].auth_type, 'full_name')
                self.assertEqual(rows[1].auth_data, 'Tyler Durden')
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_git_without_email(self):
        d = users.createUserObject(self.master,
                                   "Tyler Durden", 'git')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'Tyler Durden')
                self.assertEqual(rows[0].auth_type, 'full_name')
                self.assertEqual(rows[0].auth_data, 'Tyler Durden')
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_parseGitAuthor_with_email(self):
        author = "Tyler Durden <tyler@mayhem.net>"
        d = users.parseGitAuthor(author)
        def check(usdict):
            self.assertEqual(len(usdict), 2)
            self.assertEqual(usdict['email'], 'tyler@mayhem.net')
            self.assertEqual(usdict['full_name'], 'Tyler Durden')
        d.addCallback(check)
        return d

    def test_parseGitAuthor_without_email(self):
        author = "Tyler Durden"
        d = users.parseGitAuthor(author)
        def check(usdict):
            self.assertEqual(len(usdict), 2)
            self.assertEqual(usdict['email'], None)
            self.assertEqual(usdict['full_name'], 'Tyler Durden')
        d.addCallback(check)
        return d

    def test_parseAuthz_BasicAuth(self):
        res = [dict(username='tdurden', password='lye'),
               dict(username='bob', password='big')]
        user_authz = mock.Mock()
        user_authz.auth.userpass = [('tdurden', 'lye'), ('bob', 'big')]
        d = users.parseAuthz(user_authz)
        def check(usdict):
            return self.assertEqual(usdict, res)
        d.addCallback(check)
        return d

    def test_parseAuthz_HTPasswdAuth(self):
        res = [dict(username='tyler', password='GamXGImzG7bNQ'),
               dict(username='narrator', password='fPpd/KoR2HCts')]
        user_authz = mock.Mock()
        user_authz.auth.file = os.path.abspath(self.htfile.name)
        d = users.parseAuthz(user_authz)
        def check(usdict):
            return self.assertEqual(usdict, res)
        d.addCallback(check)
        return d

    def test_parseAuthz_HTPasswdAuth_badfile(self):
        user_authz = mock.Mock()
        user_authz.auth.file = os.path.abspath("some_temp")
        d = users.parseAuthz(user_authz)
        def check(usdict):
            return self.assertEqual(usdict, [])
        d.addCallback(check)
        return d

    def test_createUserObject_BasicAuth(self):
        # mocks the BasicAuth authz instance part we need; userpass
        user_authz = mock.Mock()
        user_authz.auth.userpass = [('tdurden', 'lye'), ('bob', 'big')]
        d = users.createUserObject(self.master, user_authz, 'authz')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'tdurden')
                self.assertEqual(rows[0].auth_type, 'username')
                self.assertEqual(rows[0].auth_data, 'tdurden')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'tdurden')
                self.assertEqual(rows[1].auth_type, 'password')
                self.assertEqual(rows[1].auth_data, 'lye')
                self.assertEqual(rows[2].id, 3)
                self.assertEqual(rows[2].uid, 3)
                self.assertEqual(rows[2].identifier, 'bob')
                self.assertEqual(rows[2].auth_type, 'username')
                self.assertEqual(rows[2].auth_data, 'bob')
                self.assertEqual(rows[3].id, 4)
                self.assertEqual(rows[3].uid, 3)
                self.assertEqual(rows[3].identifier, 'bob')
                self.assertEqual(rows[3].auth_type, 'password')
                self.assertEqual(rows[3].auth_data, 'big')
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_HTPasswdAuth(self):
        user_authz = mock.Mock()
        user_authz.auth.file = os.path.abspath(self.htfile.name)
        d = users.createUserObject(self.master, user_authz, 'authz')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'tyler')
                self.assertEqual(rows[0].auth_type, 'username')
                self.assertEqual(rows[0].auth_data, 'tyler')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'tyler')
                self.assertEqual(rows[1].auth_type, 'password')
                self.assertEqual(rows[1].auth_data, 'GamXGImzG7bNQ')
                self.assertEqual(rows[2].id, 3)
                self.assertEqual(rows[2].uid, 3)
                self.assertEqual(rows[2].identifier, 'narrator')
                self.assertEqual(rows[2].auth_type, 'username')
                self.assertEqual(rows[2].auth_data, 'narrator')
                self.assertEqual(rows[3].id, 4)
                self.assertEqual(rows[3].uid, 3)
                self.assertEqual(rows[3].identifier, 'narrator')
                self.assertEqual(rows[3].auth_type, 'password')
                self.assertEqual(rows[3].auth_data, 'fPpd/KoR2HCts')
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_HTPasswdAuth_badfile(self):
        user_authz = mock.Mock()
        user_authz.auth.file = os.path.abspath("some_temp")
        d = users.createUserObject(self.master, user_authz, 'authz')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 0)
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d
