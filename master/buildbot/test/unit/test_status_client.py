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
from buildbot.status import master, client
from buildbot.test.fake import fakedb

class TestStatusClientPerspective(unittest.TestCase):

    def makeStatusClientPersp(self):
        m = mock.Mock(name='master')
        self.db = m.db = fakedb.FakeDBConnector(self)
        m.basedir = r'C:\BASEDIR'
        s = master.Status(m) 
        persp = client.StatusClientPerspective(s)
        return persp

    def test_getBuildSets(self):
        persp = self.makeStatusClientPersp()
        self.db.insertTestData([
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn1'),
        ])

        d = persp.perspective_getBuildSets()
        def check(bslist):
            self.assertEqual(len(bslist), 1)
            self.assertEqual(bslist[0][1], 91)
            self.failUnlessIsInstance(bslist[0][0], client.RemoteBuildSet)
        d.addCallback(check)
        return d

