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

from __future__ import absolute_import, print_function

from buildbot.process.results import SUCCESS
from buildbot.steps.source.base import Source
from buildbot.test.util.integration import RunMasterBase
from twisted.internet import defer


# a simple patch which adds a Makefile
PATCH = """diff --git a/Makefile b/Makefile
new file mode 100644
index 0000000..8a5cf80
--- /dev/null
+++ b/Makefile
@@ -0,0 +1,2 @@
+all:
+\techo OK
"""

class MySource(Source):
    """A source class which only applies the patch"""
    def startVC(self, branch, revision, patch):
        self.stdio_log = self.addLogForRemoteCommands("stdio")
        d = defer.succeed(SUCCESS)
        if patch:
            d.addCallback(self.patch, patch)
        d.addCallback(self.finished)
        d.addErrback(self.failed)
        return d


class ShellMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_shell(self):
        yield self.setupConfig(masterConfig())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True, forceParams={'foo_patch_body': PATCH})
        self.assertEqual(build['buildid'], 1)
        # if makefile was not properly created, we would have a failure
        self.assertEqual(build['results'], SUCCESS)


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers, util

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            codebases=[util.CodebaseParameter("foo", patch=util.PatchParameter())],
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(MySource(codebase='foo'))
    # if the patch was applied correctly, then make will work!
    f.addStep(steps.ShellCommand(command=["make"]))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
