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


class ShellMaster(RunMasterBase):

    @defer.inlineCallbacks
    def setup_config(self):
        c = {}
        from buildbot.config import BuilderConfig
        from buildbot.plugins import schedulers
        from buildbot.plugins import steps
        from buildbot.process.factory import BuildFactory

        c['schedulers'] = [
            schedulers.AnyBranchScheduler(name="sched", builderNames=["testy"]),
            schedulers.ForceScheduler(name="force", builderNames=["testy"])
        ]

        f = BuildFactory()
        f.addStep(steps.ShellCommand(command='sleep 100', name='sleep'))
        c['builders'] = [
            BuilderConfig(name="testy", workernames=["local1"], factory=f)
        ]
        yield self.setup_master(c)

    @defer.inlineCallbacks
    def test_shell(self):
        yield self.setup_config()

        @defer.inlineCallbacks
        def newStepCallback(_, data):
            # when the sleep step start, we kill it
            if data['name'] == 'sleep':
                brs = yield self.master.data.get(('buildrequests',))
                brid = brs[-1]['buildrequestid']
                self.master.data.control(
                    'cancel', {'reason': 'cancelled by test'}, ('buildrequests', brid))

        yield self.master.mq.startConsuming(
            newStepCallback,
            ('steps', None, 'new'))

        build = yield self.doForceBuild(wantSteps=True, wantLogs=True, wantProperties=True)
        self.assertEqual(build['buildid'], 1)

        # make sure the cancel reason is transferred all the way to the step log
        cancel_logs = [log for log in build['steps'][1]["logs"] if log["name"] == "cancelled"]
        self.assertEqual(len(cancel_logs), 1)
        self.assertIn('cancelled by test', cancel_logs[0]['contents']['content'])
