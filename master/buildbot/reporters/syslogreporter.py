import syslog

from buildbot import config
from buildbot.reporters import utils
from buildbot.util import service
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS


from twisted.internet import defer


class SyslogStatusPush(service.BuildbotService):
    neededDetails = dict()
    name = "SyslogStatusPush"

    def _checkLogSeverity(self, logSeverity):
        if logSeverity not in [syslog.LOG_EMERG, syslog.LOG_ALERT,
                               syslog.LOG_CRIT, syslog.LOG_ERR,
                               syslog.LOG_WARNING, syslog.LOG_NOTICE,
                               syslog.LOG_INFO, syslog.LOG_DEBUG]:
            config.error("Please provide a valid log severity")

    def checkConfig(self, tags=None, builders=None, wantLogs=True,
                    buildSetSummary=False, identifier="buildbot",
                    cancelledSeverity=syslog.LOG_INFO,
                    exceptionSeverity=syslog.LOG_INFO,
                    failureSeverity=syslog.LOG_INFO,
                    successSeverity=syslog.LOG_INFO,
                    warningsSeverity=syslog.LOG_INFO):
        service.BuildbotService.checkConfig(self)
        if builders is not None and tags is not None:
            config.error("Please specify only builders or tags to include - " +
                         "not both.")

        for severity in [cancelledSeverity, exceptionSeverity, failureSeverity,
                         successSeverity, warningsSeverity]:
            self._checkLogSeverity(severity)

    def reconfigService(self, tags=None, builders=None, wantLogs=True,
                        buildSetSummary=False, identifier="buildbot",
                        cancelledSeverity=syslog.LOG_INFO,
                        exceptionSeverity=syslog.LOG_INFO,
                        failureSeverity=syslog.LOG_INFO,
                        successSeverity=syslog.LOG_INFO,
                        warningsSeverity=syslog.LOG_INFO):
        # If Tags and Builders are both None it will take all builds.
        self.tags = tags
        self.builders = builders
        self.wantLogs = wantLogs
        self.buildSetSummary = buildSetSummary
        self.identifier = identifier
        self.severities = {}
        self.severities[CANCELLED] = cancelledSeverity
        self.severities[EXCEPTION] = exceptionSeverity
        self.severities[FAILURE] = failureSeverity
        self.severities[SUCCESS] = successSeverity
        self.severities[WARNINGS] = warningsSeverity

    @defer.inlineCallbacks
    def startService(self):
        yield service.BuildbotService.startService(self)
        startConsuming = self.master.mq.startConsuming
        self._buildsetCompleteConsumer = yield startConsuming(
            self.buildsetComplete,
            ('buildsets', None, 'complete'))
        self._buildCompleteConsumer = yield startConsuming(
            self.buildComplete,
            ('builds', None, 'finished'))

    @defer.inlineCallbacks
    def stopService(self):
        self._buildsetCompleteConsumer.stopConsuming()
        self._buildCompleteConsumer.stopConsuming()

    @defer.inlineCallbacks
    def buildsetComplete(self, key, msg):
        if not self.buildSetSummary:
            return
        bsid = msg['bsid']
        result = yield utils.getDetailsForBuildset(
            self.master, bsid,
            wantProperties=True,
            wantSteps=True,
            wantLogs=True)

        builds = result['builds']
        buildset = result['buildset']

        builds = [build for build in builds if self.isBuildNeeded(build)]
        if builds:
            self.buildMessage(builds, buildset['results'])

    @defer.inlineCallbacks
    def buildComplete(self, key, build):
        if self.buildSetSummary:
            return

        yield utils.getDetailsForBuild(
            self.master, build,
            wantProperties=True,
            wantSteps=True,
            wantLogs=True,
            wantPreviousBuild=False)

        if build and self.isBuildNeeded(build):
            self.buildMessage(build, build['results'])

    def isBuildNeeded(self, build):
        tags = build['builder']['tags']
        if self.tags:
            return bool(set(self.tags) & set(tags))
        if self.builders:
            return build['builder']['name'] in self.builders
        return True

    @defer.inlineCallbacks
    def buildMessage(self, build, results):
        severity = self.severities[results]
        yield self.sendMessage(severity, str(build))

    def sendMessage(self, severity, message):
        syslog.openlog(self.identifier)
        syslog.syslog(severity, message)
        syslog.closelog()
