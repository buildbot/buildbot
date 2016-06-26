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

from buildbot.test.util.integration import RunMasterBase

try:
    # in the case buildbot_worker is not installed, the test will be skipped
    from buildbot_worker import version as worker_version
except ImportError:
    worker_version = None

# This integration test creates a master and worker environment
# and make sure the workerInfo mechanism is working

# When new protocols are added, make sure you update this test to exercice
# your proto implementation


class WorkerInfoMasterPb(RunMasterBase):
    proto = "pb"

    @defer.inlineCallbacks
    def test_transfer(self):
        yield self.setupConfig(masterConfig())
        # force and wait for a build to make sure the worker has successfully connected
        yield self.doForceBuild()
        # no we can query the data api to make sure the worker has connected
        # and registered this version properly
        workers = yield self.master.data.get(("workers",))

        self.assertEqual(len(workers), 1)
        self.assertEqual(workers[0]['workerinfo']['version'], worker_version)


class WorkerInfoMasterNull(WorkerInfoMasterPb):
    proto = "null"


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = BuildFactory()
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)
    ]
    return c
