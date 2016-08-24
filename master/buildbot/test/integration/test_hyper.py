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
        self.assertEqual(len(builds), 2)
        for b in builds:
            self.assertEqual(b['results'], SUCCESS)


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers

    c['schedulers'] = [
        schedulers.Triggerable(
            name="trigsched",
            builderNames=["build"]),
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    f.addStep(steps.Trigger(schedulerNames=['trigsched'],
                            waitForFinish=True,
                            updateSourceStamp=True))
    f.addStep(steps.ShellCommand(command='echo world'))
    f2 = BuildFactory()
    f2.addStep(steps.ShellCommand(command='echo ola'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["hyper1"],
                      factory=f),
        BuilderConfig(name="build",
                      workernames=["hyper1"],
                      factory=f2)]
    hyperconfig = workerhyper.Hyper.guess_config()
    if isinstance(hyperconfig, basestring):
        hyperconfig = json.load(open(hyperconfig))
    hyperhost, hyperconfig = hyperconfig['clouds'].items()[0]
    masterFQDN = os.environ.get('masterFQDN')
    c['workers'] = [
        HyperLatentWorker('hyper1', 'passwd', hyperhost, hyperconfig['accesskey'],
            hyperconfig['secretkey'], 'buildbot/buildbot-worker:master',
            masterFQDN=masterFQDN)
    ]
    # if the masterFQDN is forced (proxy case), then we use 9989 default port
    # else, we try to find a free port
    if masterFQDN is not None:
        c['protocols'] = {"pb": {"port": "tcp:9989"}}
    else:
        c['protocols'] = {"pb": {"port": "tcp:0"}}

    return c
