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
import json
import os
from unittest.case import SkipTest

from future.utils import string_types
from twisted.internet import defer

from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase
from buildbot.worker import hyper as workerhyper
from buildbot.worker.hyper import HyperLatentWorker

# This integration test creates a master and hyper worker environment,
# It requires hyper creds to be configured locally with 'hyper config'

# masterFQDN environment can be used in order to define your internet visible address
# you can use ngrok tcp 9989
# and then, according to ngrok choice of port something like:
# export masterFQDN=0.tcp.ngrok.io:17994

# following environment variable can be used to stress concurent worker startup
NUM_CONCURRENT = int(os.environ.get("HYPER_TEST_NUM_CONCURRENT_BUILD", 1))


class HyperMaster(RunMasterBase):

    def setUp(self):
        if workerhyper.Hyper is None:
            raise SkipTest("hyper is not installed")
        try:
            workerhyper.Hyper.guess_config()
        except RuntimeError:
            raise SkipTest("no default config is detected")

    @defer.inlineCallbacks
    def test_trigger(self):
        yield self.setupConfig(masterConfig(), startWorker=False)

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        builds = yield self.master.data.get(("builds",))
        # if there are some retry, there will be more builds
        self.assertEqual(len(builds), 1 + NUM_CONCURRENT)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers

    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"])]
    triggereables = []
    for i in range(NUM_CONCURRENT):
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
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["hyper0"],
                      factory=f),
        BuilderConfig(name="build",
                      workernames=["hyper" + str(i) for i in range(NUM_CONCURRENT)],
                      factory=f2)]
    hyperconfig = workerhyper.Hyper.guess_config()
    if isinstance(hyperconfig, string_types):
        hyperconfig = json.load(open(hyperconfig))
    hyperhost, hyperconfig = hyperconfig['clouds'].items()[0]
    masterFQDN = os.environ.get('masterFQDN')
    c['workers'] = [
        HyperLatentWorker('hyper' + str(i), 'passwd', hyperhost, hyperconfig['accesskey'],
                          hyperconfig['secretkey'], 'buildbot/buildbot-worker:master',
                          masterFQDN=masterFQDN)
        for i in range(NUM_CONCURRENT)
    ]
    # if the masterFQDN is forced (proxy case), then we use 9989 default port
    # else, we try to find a free port
    if masterFQDN is not None:
        c['protocols'] = {"pb": {"port": "tcp:9989"}}
    else:
        c['protocols'] = {"pb": {"port": "tcp:0"}}

    return c
