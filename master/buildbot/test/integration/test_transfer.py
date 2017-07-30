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
import shutil

from twisted.internet import defer

from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and worker environment
# and make sure the transfer steps are working

# When new protocols are added, make sure you update this test to exercise
# your proto implementation


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
        yield self.setupConfig(masterConfig())

        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], SUCCESS)
        dirContents = self.readMasterDirContents("dir")
        self.assertEqual(
            dirContents,
            {os.path.join('dir', 'file1.txt'): 'filecontent',
             os.path.join('dir', 'file2.txt'): 'filecontent2',
             os.path.join('dir', 'file3.txt'): 'filecontent2'})

        # cleanup our mess (worker is cleaned up by parent class)
        shutil.rmtree("dir")
        os.unlink("master.txt")

    @defer.inlineCallbacks
    def test_globTransfer(self):
        yield self.setupConfig(masterGlobConfig())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], SUCCESS)
        dirContents = self.readMasterDirContents("dest")
        self.assertEqual(dirContents, {
            os.path.join('dest', 'file1.txt'): 'filecontent',
            os.path.join('dest', 'notafile1.txt'): 'filecontent2',
            os.path.join('dest', 'only1.txt'): 'filecontent2'
        })

        # cleanup
        shutil.rmtree("dest")


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
    f.addStep(steps.StringDownload("filecontent", workerdest="dir/file1.txt"))
    f.addStep(steps.StringDownload("filecontent2", workerdest="dir/file2.txt"))
    f.addStep(
        steps.FileUpload(workersrc="dir/file2.txt", masterdest="master.txt"))
    f.addStep(
        steps.FileDownload(mastersrc="master.txt", workerdest="dir/file3.txt"))
    f.addStep(steps.DirectoryUpload(workersrc="dir", masterdest="dir"))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)
    ]
    return c


def masterGlobConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers
    from buildbot.steps.worker import CompositeStepMixin

    class CustomStep(steps.BuildStep, CompositeStepMixin):
        @defer.inlineCallbacks
        def run(self):
            content = yield self.getFileContentFromWorker(
                "dir/file1.txt", abandonOnFailure=True)
            assert content == "filecontent"
            defer.returnValue(SUCCESS)

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force", builderNames=["testy"])
    ]

    f = BuildFactory()
    f.addStep(steps.StringDownload("filecontent", workerdest="dir/file1.txt"))
    f.addStep(
        steps.StringDownload(
            "filecontent2", workerdest="dir/notafile1.txt"))
    f.addStep(steps.StringDownload("filecontent2", workerdest="dir/only1.txt"))
    f.addStep(
        steps.MultipleFileUpload(
            workersrcs=["dir/file*.txt", "dir/not*.txt", "dir/only?.txt"],
            masterdest="dest/",
            glob=True))
    f.addStep(CustomStep())
    c['builders'] = [
        BuilderConfig(
            name="testy", workernames=["local1"], factory=f)
    ]
    return c
