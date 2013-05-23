from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION, SKIPPED
from twisted.internet import defer
from buildbot.steps.shell import ShellCommand
import re
from buildbot.util import epoch2datetime
from buildbot.util import safeTranslate

def FormatDatetime(value):
    return value.strftime("%d_%m_%Y_%H_%M_%S_%z")

def mkdt(epoch):
    if epoch:
        return epoch2datetime(epoch)

class CheckArtifactExists(ShellCommand):
    name = "CheckArtifactExists"
    description="CheckArtifactExists"
    descriptionDone="CheckArtifactExists finished"

    def __init__(self, artifact=None, artifactDirectory=None, artifactServer=None, artifactServerDir=None, artifactServerURL=None, **kwargs):
        self.master = None
        self.build_sourcestamps = []
        self.artifact = artifact
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerURL = artifactServerURL
        self.artifactBuildrequest = None
        self.artifactPath = None
        self.artifactURL = None
        ShellCommand.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def updateSourceStamps(self):
        # every build will generate at least one sourcestamp
        sourcestamps = self.build.build_status.getSourceStamps()

        build_sourcestampsetid = sourcestamps[0].sourcestampsetid

        sourcestamps_updated = self.build.build_status.getAllGotRevisions()

        if len(sourcestamps_updated) > 0:
            for key, value in sourcestamps_updated.iteritems():
                self.build_sourcestamps.append(
                    {'b_codebase': key, 'b_revision': value, 'b_sourcestampsetid': build_sourcestampsetid})

            rowsupdated = yield self.master.db.sourcestamps.updateSourceStamps(self.build_sourcestamps)
        else:
            # when running rebuild or passing revision as parameter
            for ss in sourcestamps:
                self.build_sourcestamps.append(
                    {'b_codebase': ss.codebase, 'b_revision': ss.revision, 'b_sourcestampsetid': ss.sourcestampsetid})

    @defer.inlineCallbacks
    def createSummary(self, log):
        stdio = self.getLog('stdio').readlines()
        foundregex = re.compile(r'(%s)' % self.artifact)

        for l in stdio:
            m = foundregex.search(l)
            if (m):
                # update buildrequest (madebybrid) with self.artifactBuildrequest
                brid = self.build.builder.building[0].requests[0].id
                reuse = yield self.master.db.buildrequests.reusePreviouslyGeneratedArtifact(brid, self.artifactBuildrequest['brid'])
                artifactURL = self.artifactServerURL + "/" + self.artifactPath + "/" + self.artifact
                self.addURL(self.artifact, artifactURL)
                self.build.result = SUCCESS
                self.build.allStepsDone()
                return

        self.descriptionDone = ["Artifact not found on server %s" % self.artifactServerURL]
        return

    @defer.inlineCallbacks
    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        self.updateSourceStamps()

        if not (self.build.getProperty("clean_build", False)):
            self.artifactBuildrequest = yield self.master.db.buildrequests.getBuildRequestBySourcestamps(buildername=self.build.builder.config.name, sourcestamps=self.build_sourcestamps)

            if self.artifactBuildrequest:
                self.step_status.setText(["Artifact has been already generated"])
                self.artifactPath = "%s_%s_%s" % (self.build.builder.config.builddir,
                                                  self.artifactBuildrequest['brid'], FormatDatetime(self.artifactBuildrequest['submitted_at']))

                if self.artifactDirectory:
                    self.artifactPath += "/%s" %  self.artifactDirectory

                command = ["ssh", self.artifactServer, "cd %s;" % self.artifactServerDir, "cd ",
                               self.artifactPath, "; ls %s" % self.artifact, "; ls"]
                # ssh to the server to check if it artifact is there
                self.setCommand(command)
                ShellCommand.start(self)
                return


            self.step_status.setText(["Artifact not found"])
            self.finished(SUCCESS)
            return

        self.step_status.setText(["Skipping artifact check, making a clean build"])
        self.finished(SKIPPED)
        return

class CreateArtifactDirectory(ShellCommand):

    name = "CreateArtifactDirectory"
    description="CreateArtifactDirectory"
    descriptionDone="CreateArtifactDirectory finished"

    def __init__(self,  artifactDirectory=None, artifactServer=None, artifactServerDir=None,  **kwargs):
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        ShellCommand.__init__(self, **kwargs)

    def start(self):
        for b in self.build.builder.building:
            for br in b.requests:
                artifactPath  = "%s_%s_%s" % (self.build.builder.config.builddir,
                                              br.id, FormatDatetime(mkdt(br.submittedAt)))
                if (self.artifactDirectory):
                    artifactPath += "/%s" % self.artifactDirectory


        command = ["ssh", self.artifactServer, "cd %s;" % self.artifactServerDir, "mkdir -p ",
                    artifactPath]

        self.setCommand(command)
        ShellCommand.start(self)

class UploadArtifact(ShellCommand):

    name = "UploadArtifact"
    description="UploadArtifact"
    descriptionDone="UploadArtifact finished"

    def __init__(self, artifact=None, artifactDirectory=None, artifactServer=None, artifactServerDir=None, artifactServerURL=None, **kwargs):
        self.artifact=artifact
        self.artifactURL = None
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerURL = artifactServerURL
        ShellCommand.__init__(self, **kwargs)


    def start(self):
        for b in self.build.builder.building:
            for br in b.requests:
                artifactPath  = "%s_%s_%s" % (self.build.builder.config.builddir,
                                              br.id, FormatDatetime(mkdt(br.submittedAt)))
                if (self.artifactDirectory):
                    artifactPath += "/%s" % self.artifactDirectory


        remotelocation = self.artifactServer + ":" +self.artifactServerDir + "/" + artifactPath + "/" + self.artifact
        command = ["rsync", "-vazr", self.artifact, remotelocation]

        self.artifactURL = self.artifactServerURL + "/" + artifactPath + "/" + self.artifact
        self.addURL(self.artifact, self.artifactURL)
        self.setCommand(command)
        ShellCommand.start(self)

class DownloadArtifact(ShellCommand):
    name = "DonwloadArtifact"
    description="DonwloadArtifact"
    descriptionDone="DonwloadArtifact finished"

    def __init__(self, artifactBuilderName=None, artifact=None, artifactDirectory=None, artifactServer=None, artifactServerDir=None, TriggeredByBuilder = False, **kwargs):
        self.artifactBuilderName = artifactBuilderName
        self.artifact = artifact
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.TriggeredByBuilder = TriggeredByBuilder
        self.master = None
        ShellCommand.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        #find buildrequest dependency
        bsid = self.build.builder.building[0].requests[0].bsid

        if (self.TriggeredByBuilder):
            br = yield self.master.db.buildrequests.getBuildRequestTriggered(bsid, self.artifactBuilderName)
        else:
            br = yield self.master.db.buildrequests.getRelatedBuildRequest(bsid, self.artifactBuilderName)

        print "\n\n-- got br %s "% br

        artifactPath  = "%s_%s_%s" % (safeTranslate(self.artifactBuilderName),
                                      br['brid'], FormatDatetime(br["submitted_at"]))
        if (self.artifactDirectory):
            artifactPath += "/%s" % self.artifactDirectory

        remotelocation = self.artifactServer + ":" +self.artifactServerDir + "/" + artifactPath + "/*"

        print "\n\n-- artifact location %s" % remotelocation
        command = ["rsync", "-vazr", remotelocation, self.artifactDirectory]
        self.setCommand(command)
        ShellCommand.start(self)

from buildbot import locks

class AcquireBuildLocks(LoggingBuildStep):
    name = "AcquireBuilderLocks"
    description="AcquireBuilderLocks"
    descriptionDone="AcquireBuilderLocks finished"

    def __init__(self, hideStepIf = True, **kwargs):
        LoggingBuildStep.__init__(self, hideStepIf = hideStepIf, **kwargs)

    def start(self):
        self.step_status.setText(["Acquiring lock to complete build"])
        self.finished(SUCCESS)
        self.build.locks = self.locks
        self.build.releaseLockInstanse = self
        return

    def releaseLocks(self):
        return

class ReleaseBuildLocks(LoggingBuildStep):
    name = "ReleaseBuilderLocks"
    description="ReleaseBuilderLocks"
    descriptionDone="ReleaseBuilderLocks finished"

    def __init__(self, hideStepIf = True, **kwargs):
        self.releaseLockInstanse
        LoggingBuildStep.__init__(self, hideStepIf=hideStepIf, **kwargs)

    def start(self):
        self.step_status.setText(["Releasing build locks"])
        self.locks = self.build.locks
        self.releaseLockInstanse = self.build.releaseLockInstanse
        self.finished(SUCCESS)
        return
