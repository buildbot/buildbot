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


import os
from unittest.case import SkipTest

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase
from buildbot.worker.upcloud import UpcloudLatentWorker

# This integration test creates a master and upcloud worker environment. You
# need to have upcloud account for this to work. Running this will cost money.

# If you want to run this,
# export BBTEST_UPCLOUD_CREDS=username:password

# following environment variable can be used to stress concurrent worker startup
NUM_CONCURRENT = int(os.environ.get("BUILDBOT_TEST_NUM_CONCURRENT_BUILD", 1))


class UpcloudMaster(RunMasterBase):
    # wait 5 minutes.
    timeout = 300

    def setUp(self):
        if "BBTEST_UPCLOUD_CREDS" not in os.environ:
            raise SkipTest(
                "upcloud integration tests only run when environment variable BBTEST_UPCLOUD_CREDS"
                " is set to valid upcloud credentials ")

    @defer.inlineCallbacks
    def test_trigger(self):
        yield self.setupConfig(masterConfig(num_concurrent=1), startWorker=False)
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
                      workernames=["upcloud0"],
                      factory=f),
        BuilderConfig(name="build",
                      workernames=["upcloud" + str(i)
                                   for i in range(num_concurrent)],
                      factory=f2)]
    creds = os.environ.get('BBTEST_UPCLOUD_CREDS')
    if creds is not None:
        user, password = creds.split(":")
    else:
        raise Exception("Cannot run this test without credentials")
    masterFQDN = os.environ.get('masterFQDN', 'localhost')
    c['workers'] = []
    for i in range(num_concurrent):
        upcloud_host_config = {
            "user_data":
f"""
#!/usr/bin/env bash
groupadd -g 999 buildbot
useradd -u 999 -g buildbot -s /bin/bash -d /buildworker -m buildbot
passwd -l buildbot
apt update
apt install -y git python3 python3-dev python3-pip sudo gnupg curl
pip3 install buildbot-worker service_identity
chown -R buildbot:buildbot /buildworker
cat <<EOF >> /etc/hosts
127.0.1.1    upcloud{i}
EOF
cat <<EOF >/etc/sudoers.d/buildbot
buidbot ALL=(ALL) NOPASSWD:ALL
EOF
sudo -H -u buildbot bash -c "buildbot-worker create-worker /buildworker {masterFQDN} upcloud{i} pass"
sudo -H -u buildbot bash -c "buildbot-worker start /buildworker"
"""  # noqa pylint: disable=line-too-long
        }
        c['workers'].append(UpcloudLatentWorker('upcloud' + str(i), api_username=user,
                                                api_password=password,
                                                image='Debian GNU/Linux 9 (Stretch)',
                                                hostconfig=upcloud_host_config,
                                                masterFQDN=masterFQDN))
    # un comment for debugging what happens if things looks locked.
    # c['www'] = {'port': 8080}
    # if the masterFQDN is forced (proxy case), then we use 9989 default port
    # else, we try to find a free port
    if masterFQDN is not None:
        c['protocols'] = {"pb": {"port": "tcp:9989"}}
    else:
        c['protocols'] = {"pb": {"port": "tcp:0"}}

    return c
