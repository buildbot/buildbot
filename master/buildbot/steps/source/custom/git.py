from buildbot.steps.source.git import Git
from twisted.internet import defer
from buildbot.changes.changes import Change
from buildbot.status.results import SUCCESS

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
        sourcestamps_updated = self.build.build_status.getAllGotRevisions()

        buildLatestRev = self.build.getProperty("buildLatestRev", False)
        if type(buildLatestRev) != bool:
            buildLatestRev = (buildLatestRev.lower() == "true")

        if buildLatestRev == False:
            yield self.updateBuildSourceStamps(sourcestamps_updated)
            defer.returnValue(SUCCESS)

        self.master = self.build.builder.botmaster.parent

        # calculate rev ranges
        lastRev = yield self.master.db.sourcestamps.findLastBuildRev(self.build.builder.name,
                                                                     self.build.requests[0].id,
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
        lastChanges = revList[:50]
        totalChanges = len(revList)

        for rev in lastChanges:
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

        yield self.updateBuildSourceStamps(sourcestamps_updated, changelist, totalChanges)

        defer.returnValue(SUCCESS)
