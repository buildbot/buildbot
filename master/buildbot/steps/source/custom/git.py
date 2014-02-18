from buildbot.steps.source.git import Git
from twisted.internet import defer, utils
from buildbot.changes.changes import Change
import os

class GitCommand(Git):

    def __init__(self, **kwargs):
        self.encoding='utf-8'
        Git.__init__(self, **kwargs)

    def escapeParameter(self, param):

        if isinstance(self.buildslave.slave_environ, dict) and 'OS' in self.buildslave.slave_environ.keys() and 'windows' in self.buildslave.slave_environ['OS'].lower():
            return param.replace('%', '%%')

        return param

    @defer.inlineCallbacks
    def parseChanges(self, _):
        buildLatestRev = self.build.getProperty("buildLatestRev", False)
        if type(buildLatestRev) != bool:
            buildLatestRev = (buildLatestRev.lower() == "true")

        if buildLatestRev == False:
            defer.returnValue(0)

        self.master = self.build.builder.botmaster.parent

        sourcestamps_updated = self.build.build_status.getAllGotRevisions()
        # calculate rev ranges
        lastRev = yield self.master.db.sourcestamps.findLastBuildRev(self.build.builder.name,
                                                                     self.build.build_status.number,
                                                                     self.codebase,
                                                                     self.repourl,
                                                                     self.branch)

        currentRev  = sourcestamps_updated[self.codebase]

        revListArgs = ['log', self.escapeParameter(r'--format=%H'), '--ancestry-path', '%s..%s' % (lastRev,currentRev), '--']

        if lastRev is None or lastRev == '' or currentRev == lastRev:
            revListArgs = ['log', self.escapeParameter(r'--format=%H'), '%s' % currentRev, '-1', '--']

        results = yield self._dovccmd(revListArgs, collectStdout=True)

        revList = results.split()
        self.changeCount = len(revList)

        changelist = []

        for rev in revList:
            args = ['log','--no-walk', self.escapeParameter(r'--format=%ct'), rev, '--']
            timestamp = yield self._dovccmd(args, collectStdout=True)
            try:
                when = float(timestamp)
            except:
                when = timestamp
            args = ['log', '--no-walk', self.escapeParameter(r'--format=%aN <%aE>'), rev, '--']
            author = yield self._dovccmd(args, collectStdout=True)
            args = ['log', '--no-walk', self.escapeParameter(r'--format=%s%n%b'), rev, '--']
            comments = yield self._dovccmd(args, collectStdout=True)
            comments = comments.decode(self.encoding)

            changelist.append(Change(who=author, files=None, comments=comments, when=when, repository=self.repourl, branch= self.branch,revision=rev, codebase= self.codebase))

        sourcestamps = self.build.build_status.getSourceStamps()

        for ss in sourcestamps:
            if ss.codebase == self.codebase:
                ss.changes = changelist
                ss.revision = sourcestamps_updated[self.codebase]
                break

        # update buildrequest revision
        self.build.requests[0].sources[self.codebase].revision = sourcestamps_updated[self.codebase]

        if len(sourcestamps_updated) > 0:
            ss = [{'b_codebase': self.codebase, 'b_revision': sourcestamps_updated[self.codebase], 'b_sourcestampsetid': sourcestamps[0].sourcestampsetid}]
            result = yield self.master.db.sourcestamps.updateSourceStamps(ss)

        defer.returnValue(0)
