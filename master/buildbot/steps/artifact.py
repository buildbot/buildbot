from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION, SKIPPED
from twisted.internet import defer

class CheckArtifactExists(LoggingBuildStep):
    name = "CheckArtifactExists"

    def __init__(self, **kwargs):
        self.build_sourcestampsetid =None
        self.build_sourcestamps = []
        self.master = None
        LoggingBuildStep.__init__(self, **kwargs)

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


    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        self.updateSourceStamps()

        return self.finished(SUCCESS)