from buildbot.process.buildstep import LoggingBuildStep
from buildbot.steps.shell import ShellCommand
from buildbot.process.slavebuilder import IDLE
from buildbot.status.results import SUCCESS, RESUME
from twisted.internet import defer

class ResumeBuild(LoggingBuildStep):
    name = "Resume Build"
    description="Resume Build..."
    descriptionDone="Resume Build"

    def __init__(self, resumeBuild=True, resumeSlavepool=None, **kwargs):
        self.resumeBuild = resumeBuild if resumeBuild is not None else True
        self.resumeSlavepool = "slavenames" if resumeSlavepool is None else resumeSlavepool
        LoggingBuildStep.__init__(self, **kwargs)

    def releaseBuildLocks(self):
        self.build.releaseLocks()
        # reset the build locks
        self.build.locks = []
        #  release slave lock
        self.build.slavebuilder.state = IDLE
        self.build.builder.builder_status.setBigState("idle")

    def acquireLocks(self, res=None):
        if self.resumeBuild:
            self.releaseBuildLocks()
            return defer.succeed(None)

        return LoggingBuildStep.acquireLocks(self, res)

    def releaseLocks(self):
        if not self.resumeBuild:
            LoggingBuildStep.releaseLocks(self)

    def finished(self, results):
        if self.resumeBuild and results == SUCCESS:
            text = ["Build Will Be Resumed"]
            # saved the a resume build status
            # in this case skip the finished time ?
            self.step_status.stepFinished(SUCCESS)
            self.build.build_status.resumeSlavepool = self.resumeSlavepool
            self.build.buildFinished(text, RESUME)

        LoggingBuildStep.finished(self, results)


class ShellCommandResumeBuild(ShellCommand):
    name = "Resume Build"
    description="Resume Build..."
    descriptionDone="Resume Build"

    def __init__(self, resumeBuild=True, resumeSlavepool=None, **kwargs):
        self.resumeBuild = resumeBuild if resumeBuild is not None else True
        self.resumeSlavepool = "slavenames" if resumeSlavepool is None else resumeSlavepool
        ShellCommand.__init__(self, **kwargs)

    def releaseBuildLocks(self):
        self.build.releaseLocks()
        # reset the build locks
        self.build.locks = []
        #  release slave lock
        self.build.slavebuilder.state = IDLE
        self.build.builder.builder_status.setBigState("idle")

    def releaseLocks(self):
        if self.resumeBuild:
            self.releaseBuildLocks()
            return
        ShellCommand.releaseLocks(self)

    def finished(self, results):
        if self.resumeBuild and results == SUCCESS:
            text = ["Build Will Be Resumed"]
            # saved the a resume build status
            # in this case skip the finished time ?
            self.step_status.stepFinished(SUCCESS)
            self.build.build_status.resumeSlavepool = self.resumeSlavepool
            self.build.buildFinished(text, RESUME)

        ShellCommand.finished(self, results)
