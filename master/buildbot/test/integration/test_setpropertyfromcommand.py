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
from twisted.internet import reactor
from twisted.internet import task

from buildbot.test.util.integration import RunMasterBase

# This integration test helps reproduce http://trac.buildbot.net/ticket/3024
# we make sure that we can reconfigure the master while build is running


class SetPropertyFromCommand(RunMasterBase):

    @defer.inlineCallbacks
    def test_setProp(self):
        yield self.setupConfig(masterConfig())
        oldNewLog = self.master.data.updates.addLog

        @defer.inlineCallbacks
        def newLog(*arg, **kw):
            # Simulate db delay. We usually don't test race conditions
            # with delays, but in integrations test, that would be pretty
            # tricky
            yield task.deferLater(reactor, .1, lambda: None)
            res = yield oldNewLog(*arg, **kw)
            defer.returnValue(res)
        self.master.data.updates.addLog = newLog
        build = yield self.doForceBuild(wantProperties=True)

        self.assertEqual(
            build['properties']['test'], (u'foo', u'SetPropertyFromCommand Step'))


# master configuration

num_reconfig = 0


def masterConfig():
    global num_reconfig
    num_reconfig += 1
    c = {}
    from buildbot.plugins import schedulers, steps, util

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = util.BuildFactory()
    f.addStep(steps.SetPropertyFromCommand(
        property="test", command=["echo", "foo"]))
    c['builders'] = [
        util.BuilderConfig(name="testy",
                           workernames=["local1"],
                           factory=f)]

    return c
