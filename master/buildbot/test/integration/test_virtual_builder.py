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

from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with one builder and a shellcommand step
# meant to be a template for integration steps
class ShellMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_shell(self):
        yield self.setupConfig(masterConfig())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        builders = yield self.master.data.get(("builders",))
        self.assertEqual(len(builders), 2)
        self.assertEqual(builders[1], {
            'masterids': [], 'tags': [u'virtual'], 'description': u'I am a virtual builder',
            'name': u'virtual_testy', 'builderid': 2})
        self.assertEqual(build['builderid'], builders[1]['builderid'])


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      properties={
                          'virtual_builder_name': 'virtual_testy',
                          'virtual_builder_description': 'I am a virtual builder',
                          'virtual_builder_tags': ['virtual'],
                      },
                      factory=f)]
    return c
