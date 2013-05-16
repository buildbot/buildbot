from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION, SKIPPED
from twisted.internet import defer
from buildbot.steps.shell import ShellCommand
import re

def FormatDatetime(value):
    return value.strftime("%d_%m_%Y_%H_%M_%S_%z")

class CheckArtifactExists(ShellCommand):
    name = "CheckArtifactExists"
    description="CheckArtifactExists"
    descriptionDone="CheckArtifactExists finished"

    def __init__(self, artifact=None, artifactDirectory=None, artifactServer=None, artifactServerDir=None, artifactServerURL=None, **kwargs):
        self.build_sourcestampsetid =None
        self.build_sourcestamps = []
        self.master = None
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

        self.build_sourcestampsetid = sourcestamps[0].sourcestampsetid

        sourcestamps_updated = self.build.build_status.getAllGotRevisions()

        if len(sourcestamps_updated) > 0:
            for key, value in sourcestamps_updated.iteritems():
                self.build_sourcestamps.append(
                    {'b_codebase': key, 'b_revision': value, 'b_sourcestampsetid': self.build_sourcestampsetid})

            rowsupdated = yield self.master.db.sourcestamps.updateSourceStamps(self.build_sourcestamps)
        else:
            # when running rebuild or passing revision as parameter
            for ss in sourcestamps:
                self.build_sourcestamps.append(
                    {'b_codebase': ss.codebase, 'b_revision': ss.revision, 'b_sourcestampsetid': ss.sourcestampsetid})

    def createSummary(self, log):
        stdio = self.getLog('stdio').readlines()
        foundregex = re.compile(r'(%s)' % self.artifact)

        for l in stdio:
            m = foundregex.search(l)
            if (m):
                # update buildrequest (madebybrid)
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
                self.artifactPath = "%s_%s_%s" % (self.build.builder.config.builddir, self.artifactBuildrequest['brid'], FormatDatetime(self.artifactBuildrequest['submitted_at']))

                if self.artifactDirectory:
                    self.artifactPath += "/%s" %  self.artifactDirectory

                command = ["ssh", self.artifactServer, "cd %s;" % self.artifactServerDir, "cd ",
                               self.artifactPath, "; ls %s" % self.artifact, "; ls"]

                self.setCommand(command)
                # ssh to the server to check if it artifact is there
                ShellCommand.start(self)
                return


            self.step_status.setText(["Artifact not found"])
            self.finished(SUCCESS)
            return

        self.step_status.setText(["Skipping artifact check, making a clean build"])
        self.finished(SKIPPED)
        return