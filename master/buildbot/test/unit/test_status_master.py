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
from buildbot.status import master
from buildbot.test.fake import fakedb

class TestStatus(unittest.TestCase):

    def makeStatus(self):
        m = mock.Mock(name='master')
        self.db = m.db = fakedb.FakeDBConnector(self)
        m.basedir = r'C:\BASEDIR'
        s = master.Status(m)
        return s

    def test_getBuildSets(self):
        s = self.makeStatus()
        self.db.insertTestData([
            fakedb.Buildset(id=91, sourcestampid=234, complete=0,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn1'),
            fakedb.Buildset(id=92, sourcestampid=234, complete=1,
                    complete_at=298297876, results=7, submitted_at=266761876,
                    external_idstring='extid', reason='rsn2'),
        ])

        d = s.getBuildSets()
        def check(bslist):
            self.assertEqual([ bs.id for bs in bslist ], [ 91 ])
        d.addCallback(check)
        return d
