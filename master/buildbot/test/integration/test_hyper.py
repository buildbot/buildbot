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
from future.utils import string_types

import json
import os
from unittest.case import SkipTest

from twisted.internet import defer

from buildbot import util
from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.test.fake.step import BuildStepController
from buildbot.test.util.integration import RunMasterBase
from buildbot.worker import hyper as workerhyper
from buildbot.worker.hyper import HyperLatentWorker

# This integration test creates a master and hyper worker environment,
# It requires hyper creds to be configured locally with 'hyper config'

# masterFQDN environment can be used in order to define your internet visible address
# you can use ngrok tcp 9989
# and then, according to ngrok choice of port something like:
# export masterFQDN=0.tcp.ngrok.io:17994

# following environment variable can be used to stress concurrent worker startup
NUM_CONCURRENT = int(os.environ.get("HYPER_TEST_NUM_CONCURRENT_BUILD", 1))


class HyperMaster(RunMasterBase):

    def setUp(self):
        if "TEST_HYPER" not in os.environ:
            raise SkipTest(
                "hyper integration tests only run when environment variable TEST_HYPER is set")
        if workerhyper.Hyper is None:
            raise SkipTest("hyper is not installed")
        try:
            workerhyper.Hyper.guess_config()
        except RuntimeError:
            raise SkipTest("no default config is detected")

    @defer.inlineCallbacks
    def test_trigger(self):
        yield self.setupConfig(masterConfig(num_concurrent=NUM_CONCURRENT), startWorker=False)
        yield self.doForceBuild()

        builds = yield self.master.data.get(("builds",))
        # if there are some retry, there will be more builds
        self.assertEqual(len(builds), 1 + NUM_CONCURRENT)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)

    @defer.inlineCallbacks
    def test_trigger_controlled_step(self):
        stepcontroller = BuildStepController()
        yield self.setupConfig(masterConfig(num_concurrent=1, extra_steps=[stepcontroller.step]),
                               startWorker=False)

        d = self.doForceBuild()
        builds = []
        while len(builds) != 2:
            builds = yield self.master.data.get(("builds",))
            util.asyncSleep(.1)

        while not stepcontroller.running:
            yield util.asyncSleep(.1)

        stepcontroller.finish_step(SUCCESS)
        yield d
        builds = yield self.master.data.get(("builds",))
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)

    @defer.inlineCallbacks
    def test_trigger_controlled_step_killing_worker_in_between(self):
        stepcontroller = BuildStepController()
        yield self.setupConfig(masterConfig(num_concurrent=1, extra_steps=[stepcontroller.step]),
                               startWorker=False)

        d = self.doForceBuild()
        builds = []
        while len(builds) != 2:
            builds = yield self.master.data.get(("builds",))
            yield util.asyncSleep(.1)

        while not stepcontroller.running:
            yield util.asyncSleep(.1)

        worker = self.master.workers.workers['hyper0']
        worker.client.remove_container(worker.instance['Id'], v=True, force=True)

        # wait that the build is retried
        while len(builds) == 2:
            builds = yield self.master.data.get(("builds",))
            yield util.asyncSleep(.1)
        stepcontroller.auto_finish_step(SUCCESS)

        yield d
        builds = yield self.master.data.get(("builds",))
        self.assertEqual(len(builds), 5, msg=None)
        # the two first builds were retried
        self.assertEqual(builds[0]['results'], RETRY)
        self.assertEqual(builds[1]['results'], RETRY)
        self.assertEqual(builds[2]['results'], SUCCESS)
        self.assertEqual(builds[3]['results'], SUCCESS)
        self.assertEqual(builds[4]['results'], SUCCESS)

    @defer.inlineCallbacks
    def test_trigger_controlled_step_stopped_worker_in_between(self):
        stepcontroller = BuildStepController()
        yield self.setupConfig(masterConfig(num_concurrent=1, extra_steps=[stepcontroller.step]),
                               startWorker=False)

        d = self.doForceBuild()
        builds = []
        while len(builds) != 2:
            builds = yield self.master.data.get(("builds",))
            yield util.asyncSleep(.1)

        while not stepcontroller.running:
            yield util.asyncSleep(.1)

        worker = self.master.workers.workers['hyper0']
        worker.client.stop(worker.instance['Id'])
        # wait that the build is retried
        while len(builds) == 2:
            builds = yield self.master.data.get(("builds",))
            yield util.asyncSleep(.1)
        stepcontroller.auto_finish_step(SUCCESS)

        yield d
        builds = yield self.master.data.get(("builds",))
        self.assertEqual(len(builds), 5, msg=None)
        # the two first builds were retried
        self.assertEqual(builds[0]['results'], RETRY)
        self.assertEqual(builds[1]['results'], RETRY)
        self.assertEqual(builds[2]['results'], SUCCESS)
        self.assertEqual(builds[3]['results'], SUCCESS)
        self.assertEqual(builds[4]['results'], SUCCESS)


# master configuration
def masterConfig(num_concurrent, extra_steps=None):
    if extra_steps is None:
        extra_steps = []
    c = {}

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]
    triggereables = []
    for i in range(num_concurrent):
        c['schedulers'].append(
            schedulers.Triggerable(
                name="trigsched" + str(i),
                builderNames=["build"]))
        triggereables.append("trigsched" + str(i))

    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    f.addStep(steps.Trigger(schedulerNames=triggereables,
                            waitForFinish=True,
                            updateSourceStamp=True))
    f.addStep(steps.ShellCommand(command='echo world'))
    f2 = BuildFactory()
    f2.addStep(steps.ShellCommand(command='echo ola'))
    for step in extra_steps:
        f2.addStep(step)
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["hyper0"],
                      factory=f),
        BuilderConfig(name="build",
                      workernames=["hyper" + str(i)
                                   for i in range(num_concurrent)],
                      factory=f2)]
    hyperconfig = workerhyper.Hyper.guess_config()
    if isinstance(hyperconfig, string_types):
        hyperconfig = json.load(open(hyperconfig))
    hyperhost, hyperconfig = hyperconfig['clouds'].items()[0]
    masterFQDN = os.environ.get('masterFQDN')
    c['workers'] = [
        HyperLatentWorker('hyper' + str(i), 'passwd', hyperhost, hyperconfig['accesskey'],
                          hyperconfig[
                              'secretkey'], 'buildbot/buildbot-worker:master',
                          masterFQDN=masterFQDN)
        for i in range(num_concurrent)
    ]
    # un comment for debugging what happens if things looks locked.
    # c['www'] = {'port': 8080}
    # if the masterFQDN is forced (proxy case), then we use 9989 default port
    # else, we try to find a free port
    if masterFQDN is not None:
        c['protocols'] = {"pb": {"port": "tcp:9989"}}
    else:
        c['protocols'] = {"pb": {"port": "tcp:0"}}

    return c
