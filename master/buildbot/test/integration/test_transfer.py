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
import shutil

from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase
from twisted.internet import defer

# This integration test creates a master and slave environment
# and make sure the transfer steps are working

# When new protocols are added, make sure you update this test to exercice your proto implementation


class TransferStepsMasterPb(RunMasterBase):
    proto = "pb"

    def readMasterDirContents(self, top):
        contents = {}
        for root, dirs, files in os.walk(top):
            for name in files:
                fn = os.path.join(root, name)
                with open(fn) as f:
                    contents[fn] = f.read()
        return contents

    @defer.inlineCallbacks
    def test_transfer(self):

        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], SUCCESS)
        dirContents = self.readMasterDirContents("dir")
        self.assertEqual(
            dirContents,
            {'dir/file1.txt': 'filecontent',
             'dir/file2.txt': 'filecontent2',
             'dir/file3.txt': 'filecontent2'})

        # cleanup our mess (slave is cleaned up by parent class)
        shutil.rmtree("dir")
        os.unlink("master.txt")


class TransferStepsMasterNull(TransferStepsMasterPb):
    proto = "null"


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
    # do a bunch of transfer to exercise the protocol
    f.addStep(steps.StringDownload("filecontent", slavedest="dir/file1.txt"))
    f.addStep(steps.StringDownload("filecontent2", slavedest="dir/file2.txt"))
    f.addStep(steps.FileUpload(slavesrc="dir/file2.txt", masterdest="master.txt"))
    f.addStep(steps.FileDownload(mastersrc="master.txt", slavedest="dir/file3.txt"))
    f.addStep(steps.DirectoryUpload(slavesrc="dir", masterdest="dir"))
    c['builders'] = [
        BuilderConfig(name="testy",
                      slavenames=["local1"],
                      factory=f)
    ]
    return c
