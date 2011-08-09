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

from buildbot.process.users import users
from buildbot.db import users as db_users
from buildbot.test.util import connector_component


class UsersTests(connector_component.ConnectorComponentMixin,
                 unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(table_names=['users', 'users_info'])
        def finish_setup(_):
            self.master = mock.Mock()
            self.db.users = db_users.UsersConnectorComponent(self.db)
            self.master.db.users = self.db.users
        d.addCallback(finish_setup)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def test_createUserObject_no_src(self):
        d = users.createUserObject(self.master, "Tyler Durden", None)
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 0)
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_unrecognized_src(self):
        d = users.createUserObject(self.master, "Tyler Durden", 'blah')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 0)
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_git(self):
        d = users.createUserObject(self.master,
                                   "Tyler Durden <tyler@mayhem.net>", 'git')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                r = conn.execute(self.db.model.users_info.select())
                info_rows = r.fetchall()

                self.assertEqual(len(rows), 1)
                self.assertEqual(len(info_rows), 1)

                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier,
                                 'Tyler Durden <tyler@mayhem.net>')
                self.assertEqual(info_rows[0].uid, 1)
                self.assertEqual(info_rows[0].attr_type, 'git')
                self.assertEqual(info_rows[0].attr_data,
                                 'Tyler Durden <tyler@mayhem.net>')
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createUserObject_svn(self):
        d = users.createUserObject(self.master, "tdurden", 'svn')
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                r = conn.execute(self.db.model.users_info.select())
                info_rows = r.fetchall()

                self.assertEqual(len(rows), 1)
                self.assertEqual(len(info_rows), 1)

                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'tdurden')
                self.assertEqual(info_rows[0].uid, 1)
                self.assertEqual(info_rows[0].attr_type, 'svn')
                self.assertEqual(info_rows[0].attr_data, 'tdurden')
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d
