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

from twisted.internet import defer

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.test.util.decorators import flaky
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

    def get_config_single_step(self, step):
        c = {}
        from buildbot.config import BuilderConfig
        from buildbot.process.factory import BuildFactory
        from buildbot.plugins import steps, schedulers

        c['schedulers'] = [
            schedulers.ForceScheduler(
                name="force",
                builderNames=["testy"])]

        f = BuildFactory()

        f.addStep(steps.FileUpload(workersrc="dir/noexist_path", masterdest="master_dest"))
        c['builders'] = [
            BuilderConfig(name="testy",
                          workernames=["local1"],
                          factory=f)
        ]
        return c

    def get_non_existing_file_upload_config(self):
        from buildbot.plugins import steps
        step = steps.FileUpload(workersrc="dir/noexist_path", masterdest="master_dest")
        return self.get_config_single_step(step)

    def get_non_existing_directory_upload_config(self):
        from buildbot.plugins import steps
        step = steps.DirectoryUpload(workersrc="dir/noexist_path", masterdest="master_dest")
        return self.get_config_single_step(step)

    def get_non_existing_multiple_file_upload_config(self):
        from buildbot.plugins import steps
        step = steps.MultipleFileUpload(workersrcs=["dir/noexist_path"], masterdest="master_dest")
        return self.get_config_single_step(step)

    @flaky(bugNumber=4407, onPlatform='win32')
    @defer.inlineCallbacks
    def test_transfer(self):
        yield self.setupConfig(masterConfig(bigfilename=self.mktemp()))

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

    @defer.inlineCallbacks
    def test_no_exist_file_upload(self):
        yield self.setupConfig(self.get_non_existing_file_upload_config())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], FAILURE)
        res = yield self.checkBuildStepLogExist(build, "Cannot open file")
        self.assertTrue(res)

    @defer.inlineCallbacks
    def test_no_exist_directory_upload(self):
        yield self.setupConfig(self.get_non_existing_directory_upload_config())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], FAILURE)
        res = yield self.checkBuildStepLogExist(build, "Cannot open file")
        self.assertTrue(res)

    @defer.inlineCallbacks
    def test_no_exist_multiple_file_upload(self):
        yield self.setupConfig(self.get_non_existing_multiple_file_upload_config())
        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], FAILURE)
        res = yield self.checkBuildStepLogExist(build, "Cannot open file")
        self.assertTrue(res)


class TransferStepsMasterNull(TransferStepsMasterPb):
    proto = "null"


# master configuration
def masterConfig(bigfilename):
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
    # create 8 MB file
    with open(bigfilename, 'w') as o:
        buf = "xxxxxxxx" * 1024
        for i in range(1000):
            o.write(buf)
    f.addStep(
        steps.FileDownload(
            mastersrc=bigfilename, workerdest="bigfile.txt"))
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
            return SUCCESS

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
