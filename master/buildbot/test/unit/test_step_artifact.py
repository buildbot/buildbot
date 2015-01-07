from twisted.trial import unittest
from buildbot.test.util import steps

from buildbot.steps import artifact
from buildbot.status.results import SUCCESS
from buildbot.test.fake.remotecommand import ExpectShell

from buildbot.test.fake import fakedb

class TestArtifactSteps(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, step):
        steps.BuildStepMixin.setupStep(self, step)

        fake_br = fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0)
        fake_br.submittedAt = 1418823086
        self.build.requests = [fake_br]
        self.build.builder.config.builddir = "build"



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
                        command=['rsync', '-var', 'myartifact.py',
                                 'usr@srv.com:/home/srv/web/dir/build_1_17_12_2014_13_31_26_+0000/mydir/myartifact.py'])
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()
