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

import os
from unittest.case import SkipTest

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase
from buildbot.worker.marathon import MarathonLatentWorker

# This integration test creates a master and marathon worker environment,
# It requires environment variable set to your marathon hosting.
# you can use the mesos-compose to create a marathon environment for development:

# git clone https://github.com/bobrik/mesos-compose.git
# cd mesos-compose
# make run

# then set the environment variable to run the test:
# export BBTEST_MARATHON_URL=http://localhost:8080

# following environment variable can be used to stress concurrent worker startup
NUM_CONCURRENT = int(os.environ.get("MARATHON_TEST_NUM_CONCURRENT_BUILD", 1))

# if you run the stress test against a real mesos deployment, you want to also use https and basic credentials
# export BBTEST_MARATHON_CREDS=login:passwd


class MarathonMaster(RunMasterBase):

    def setUp(self):
        if "BBTEST_MARATHON_URL" not in os.environ:
            raise SkipTest(
                "marathon integration tests only run when environment variable BBTEST_MARATHON_URL"
                " is with url to Marathon api ")

    @defer.inlineCallbacks
    def test_trigger(self):
        yield self.setupConfig(masterConfig(num_concurrent=NUM_CONCURRENT), startWorker=False)
        yield self.doForceBuild()

        builds = yield self.master.data.get(("builds",))
        # if there are some retry, there will be more builds
        self.assertEqual(len(builds), 1 + NUM_CONCURRENT)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)


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
                      workernames=["marathon0"],
                      factory=f),
        BuilderConfig(name="build",
                      workernames=["marathon" + str(i)
                                   for i in range(num_concurrent)],
                      factory=f2)]
    url = os.environ.get('BBTEST_MARATHON_URL')
    creds = os.environ.get('BBTEST_MARATHON_CREDS')
    if creds is not None:
        user, password = creds.split(":")
    else:
        user = password = None
    masterFQDN = os.environ.get('masterFQDN')
    marathon_extra_config = {
    }
    c['workers'] = [
        MarathonLatentWorker('marathon' + str(i), url, user, password, 'buildbot/buildbot-worker:master',
                             marathon_extra_config=marathon_extra_config,
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
