from twisted.trial import unittest
from buildbot.test.util import steps

from buildbot.steps import artifact
from buildbot.status.results import SUCCESS
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.fake import fakemaster, fakedb

class TestArtifactSteps(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, step, brqs=None, winslave=False):
        steps.BuildStepMixin.setupStep(self, step)

        fake_br = fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0)
        fake_br.submittedAt = 1418823086
        self.build.requests = [fake_br]
        self.build.builder.config.builddir = "build"

        m = fakemaster.make_master()
        self.build.builder.botmaster = m.botmaster
        m.db = fakedb.FakeDBConnector(self)

        breqs = [fake_br]
        if brqs:
            breqs += brqs

        self.build.slavebuilder.slave.slave_environ = {}

        if winslave:
            self.build.slavebuilder.slave.slave_environ['os'] = 'Windows_NT'

        m.db.insertTestData(breqs)



    def test_create_artifact_directory(self):
        self.setupStep(artifact.CreateArtifactDirectory(artifactDirectory="mydir",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['ssh','usr@srv.com', 'cd /home/srv/web/dir;', 'mkdir -p ',
                                 'build_1_17_12_2014_13_31_26_+0000/mydir'])
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Remote artifact directory created.'])
        return self.runStep()

    def test_upload_artifact(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                   artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                   artifactServerURL="http://srv.com/dir"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='n=0; false; until [[ $? -eq 0 || $n -ge 5 ]]; do n=$[$n+1]; sleep 5; '+
                                'rsync -var --partial myartifact.py'+
                                ' usr@srv.com:/home/srv/web/dir/build_1_17_12_2014_13_31_26_+0000/mydir/myartifact.py;'+
                                ' done')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()

    def test_upload_artifact_Win(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                   artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                   artifactServerURL="http://srv.com/dir"), winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for /L %%i in (1,1,5) do (sleep 5 & rsync -var --partial '+
                                'myartifact.py '+
                                'usr@srv.com:/home/srv/web/dir/build_1_17_12_2014_13_31_26_+0000/mydir/myartifact.py'+
                                ' && exit 0)')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()

    def test_download_artifact(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                     artifactDirectory="mydir",
                                     artifactServer='usr@srv.com',
                                     artifactServerDir='/home/srv/web/dir'), [fake_trigger])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='n=0; false; until [[ $? -eq 0 || $n -ge 5 ]]; '+
                                'do n=$[$n+1]; sleep 5; rsync -var --partial '+
                                'usr@srv.com:/home/srv/web/dir/B_2_01_01_1970_00_00_00_+0000/mydir/myartifact.py'+
                                ' myartifact.py; done')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()


    def test_download_artifact_Win(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                     artifactDirectory="mydir",
                                     artifactServer='usr@srv.com',
                                     artifactServerDir='/home/srv/web/dir'), [fake_trigger], winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for /L %%i in (1,1,5) do (sleep 5 & rsync -var --partial '+
                                'usr@srv.com:/home/srv/web/dir/B_2_01_01_1970_00_00_00_+0000/mydir/myartifact.py'+
                                ' myartifact.py && exit 0)')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()


    def test_download_artifact_reusing_build(self):
        fake_br2 = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1, submitted_at=1418823086,
                                           results=0, triggeredbybrid=0, startbrid=0)
        fake_trigger = fakedb.BuildRequest(id=3, buildsetid=3, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1, artifactbrid=2)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                     artifactDirectory="mydir",
                                     artifactServer='usr@srv.com',
                                     artifactServerDir='/home/srv/web/dir'), [fake_br2, fake_trigger])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='n=0; false; until [[ $? -eq 0 || $n -ge 5 ]]; '+
                                'do n=$[$n+1]; sleep 5; rsync -var --partial'+
                                ' usr@srv.com:/home/srv/web/dir/B_2_17_12_2014_13_31_26_+0000/mydir/myartifact.py'+
                                ' myartifact.py; done')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

