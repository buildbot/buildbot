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

from twisted.internet import defer
from twisted.python import log
from twisted.python import threadpool
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from buildbot.config import BuilderConfig
from buildbot.plugins import util
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.test.fake.step import BuildStepController
from buildbot.test.util.integration import getMaster
from buildbot.util.eventual import _setReactor
from buildbot.util.eventual import flushEventualQueue
from buildbot.worker.local import LocalWorker


class Tests(TestCase):

    def setUp(self):
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()
        self.addCleanup(self.reactor.stop)
        _setReactor(self.reactor)
        self.addCleanup(_setReactor, None)

        # to ease debugging we display the error logs in the test log
        origAddCompleteLog = BuildStep.addCompleteLog

        def addCompleteLog(self, name, _log):
            if name.endswith("err.text"):
                log.msg("got error log!", name, _log)
            return origAddCompleteLog(self, name, _log)
        self.patch(BuildStep, "addCompleteLog", addCompleteLog)

    def tearDown(self):
        self.assertFalse(self.master.running, "master is still running!")

    @defer.inlineCallbacks
    def getMaster(self, config_dict):
        self.master = master = yield getMaster(self, self.reactor, config_dict)
        defer.returnValue(master)

    def createLocalWorker(self, name):
        workdir = FilePath(self.mktemp())
        workdir.createDirectory()
        return LocalWorker(name, workdir.path)

    def createBuildrequest(self, master, builder_ids, properties=None):
        # returns a Deferred

        properties = properties.asDict() if properties is not None else None
        return master.data.updates.addBuildset(
            waited_for=False,
            builderids=builder_ids,
            sourcestamps=[
                {'codebase': '',
                 'repository': '',
                 'branch': None,
                 'revision': None,
                 'project': ''},
            ],
            properties=properties,
        )

    @defer.inlineCallbacks
    def test_builder_lock_release_wakes_builds_for_another_builder(self):
        """
        If a builder locks a master lock then the build request distributor
        must retry running any buildrequests that might have been not scheduled
        due to unavailability of that lock when the lock becomes available.
        """

        stepcontroller1 = BuildStepController()
        stepcontroller2 = BuildStepController()

        master_lock = util.MasterLock("lock1", maxCount=1)

        config_dict = {
            'builders': [
                BuilderConfig(name='builder1',
                              workernames=['worker1'],
                              factory=BuildFactory([stepcontroller1.step]),
                              locks=[master_lock.access('counting')]),
                BuilderConfig(name='builder2',
                              workernames=['worker2'],
                              factory=BuildFactory([stepcontroller2.step]),
                              locks=[master_lock.access('counting')]),
            ],
            'workers': [
                self.createLocalWorker('worker1'),
                self.createLocalWorker('worker2'),
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        master = yield self.getMaster(config_dict)
        builder1_id = yield master.data.updates.findBuilderId('builder1')
        builder2_id = yield master.data.updates.findBuilderId('builder2')

        # start two builds and verify that a second build starts after the
        # first is finished
        yield self.createBuildrequest(master, [builder1_id])
        yield self.createBuildrequest(master, [builder2_id])

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]['results'], None)
        self.assertEqual(builds[0]['builderid'], builder1_id)

        stepcontroller1.finish_step(SUCCESS)

        # execute Build.releaseLocks which is called eventually
        yield flushEventualQueue()

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], SUCCESS)
        self.assertEqual(builds[1]['results'], None)
        self.assertEqual(builds[1]['builderid'], builder2_id)

        stepcontroller2.finish_step(SUCCESS)

        builds = yield master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        self.assertEqual(builds[0]['results'], SUCCESS)
        self.assertEqual(builds[1]['results'], SUCCESS)
