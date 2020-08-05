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

from twisted.internet import defer

from buildbot.test.fakedb.build_data import FakeBuildDataComponent
from buildbot.test.fakedb.builders import FakeBuildersComponent
from buildbot.test.fakedb.buildrequests import FakeBuildRequestsComponent
from buildbot.test.fakedb.builds import FakeBuildsComponent
from buildbot.test.fakedb.buildsets import FakeBuildsetsComponent
from buildbot.test.fakedb.changes import FakeChangesComponent
from buildbot.test.fakedb.changesources import FakeChangeSourcesComponent
from buildbot.test.fakedb.logs import FakeLogsComponent
from buildbot.test.fakedb.masters import FakeMastersComponent
from buildbot.test.fakedb.row import Row
from buildbot.test.fakedb.schedulers import FakeSchedulersComponent
from buildbot.test.fakedb.sourcestamps import FakeSourceStampsComponent
from buildbot.test.fakedb.state import FakeStateComponent
from buildbot.test.fakedb.steps import FakeStepsComponent
from buildbot.test.fakedb.tags import FakeTagsComponent
from buildbot.test.fakedb.test_result_sets import FakeTestResultSetsComponent
from buildbot.test.fakedb.test_results import FakeTestResultsComponent
from buildbot.test.fakedb.users import FakeUsersComponent
from buildbot.test.fakedb.workers import FakeWorkersComponent
from buildbot.util import service


class FakeDBConnector(service.AsyncMultiService):

    """
    A stand-in for C{master.db} that operates without an actual database
    backend.  This also implements a test-data interface similar to the
    L{buildbot.test.util.db.RealDatabaseMixin.insertTestData} method.

    The child classes implement various useful assertions and faking methods;
    see their documentation for more.
    """

    def __init__(self, testcase):
        super().__init__()
        # reset the id generator, for stable id's
        Row._next_id = 1000
        self.t = testcase
        self.checkForeignKeys = False
        self._components = []
        self.changes = comp = FakeChangesComponent(self, testcase)
        self._components.append(comp)
        self.changesources = comp = FakeChangeSourcesComponent(self, testcase)
        self._components.append(comp)
        self.schedulers = comp = FakeSchedulersComponent(self, testcase)
        self._components.append(comp)
        self.sourcestamps = comp = FakeSourceStampsComponent(self, testcase)
        self._components.append(comp)
        self.buildsets = comp = FakeBuildsetsComponent(self, testcase)
        self._components.append(comp)
        self.workers = comp = FakeWorkersComponent(self, testcase)
        self._components.append(comp)
        self.state = comp = FakeStateComponent(self, testcase)
        self._components.append(comp)
        self.buildrequests = comp = FakeBuildRequestsComponent(self, testcase)
        self._components.append(comp)
        self.builds = comp = FakeBuildsComponent(self, testcase)
        self._components.append(comp)
        self.build_data = comp = FakeBuildDataComponent(self, testcase)
        self._components.append(comp)
        self.steps = comp = FakeStepsComponent(self, testcase)
        self._components.append(comp)
        self.logs = comp = FakeLogsComponent(self, testcase)
        self._components.append(comp)
        self.users = comp = FakeUsersComponent(self, testcase)
        self._components.append(comp)
        self.masters = comp = FakeMastersComponent(self, testcase)
        self._components.append(comp)
        self.builders = comp = FakeBuildersComponent(self, testcase)
        self._components.append(comp)
        self.tags = comp = FakeTagsComponent(self, testcase)
        self._components.append(comp)
        self.test_results = comp = FakeTestResultsComponent(self, testcase)
        self._components.append(comp)
        self.test_result_sets = comp = FakeTestResultSetsComponent(self, testcase)
        self._components.append(comp)

    def setup(self):
        self.is_setup = True
        return defer.succeed(None)

    def insertTestData(self, rows):
        """Insert a list of Row instances into the database; this method can be
        called synchronously or asynchronously (it completes immediately) """
        for row in rows:
            if self.checkForeignKeys:
                row.checkForeignKeys(self, self.t)
            for comp in self._components:
                comp.insertTestData([row])
        return defer.succeed(None)
