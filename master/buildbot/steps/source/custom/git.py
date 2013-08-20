from buildbot.steps.source.git import Git
from twisted.internet import defer
from twisted.python import log
from buildbot.util import epoch2datetime

class GitCommand(Git):

    def __init__(self, **kwargs):
        self.encoding='utf-8'
        Git.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def parseChanges(self, _):
        self.master = self.build.builder.botmaster.parent

        sourcestamps_updated = self.build.build_status.getAllGotRevisions()
        # calculate rev ranges
        lastRev = yield self.master.db.sourcestamps.findLastBuildRev(self.build.builder.name, self.codebase, self.repourl, self.branch)

        currentRev  = sourcestamps_updated[self.codebase]

        revListArgs = ['log', r'--format=%H', '%s..%s' % (lastRev, currentRev), '--']

        if lastRev is None or lastRev == '' or currentRev == lastRev:
            revListArgs = ['log', r'--format=%H', '%s' % currentRev, '-1', '--']

        results = yield self._dovccmd(revListArgs, collectStdout=True)

        print "\n results %s \n" % results

        revList = results.split()
        revList.reverse()
        self.changeCount = len(revList)

        for rev in revList:
            args = ['log','--no-walk', r'--format=%ct', rev, '--']
            timestamp = yield self._dovccmd(args, collectStdout=True)
            print "\n timestamp %s \n" % epoch2datetime(timestamp)


        defer.returnValue(0)

    def _get_commit_comments(self, rev):
        args = ['log', '--no-walk', r'--format=%s%n%b', rev, '--']
        d = self._dovccmd(args, collectStdout=True)
        def process(git_output):
            git_output = git_output.decode(self.encoding)
            if len(git_output) == 0:
                raise EnvironmentError('could not get commit comment for rev')
            return git_output
        d.addCallback(process)
        return d

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['log','--no-walk', r'--format=%ct', rev, '--']
        d = self._dovccmd(args, collectStdout=True)
        def process(git_output):
            try:
                stamp = float(git_output)
            except Exception, e:
                log.msg('gitpoller: caught exception converting output \'%s\' to timestamp' % git_output)
                raise e
            return stamp

        d.addCallback(process)
        return d

    def _get_commit_files(self, rev):
        args = ['log', '--name-only', '--no-walk', r'--format=%n', rev, '--']
        d = self._dovccmd(args, collectStdout=True)
        def process(git_output):
            fileList = git_output.split()
            return fileList
        d.addCallback(process)
        return d

    def _get_commit_author(self, rev):
        args = ['log', '--no-walk', r'--format="%aN <%aE>"', rev, '--']
        d = self._dovccmd(args, collectStdout=True)
        def process(git_output):
            git_output = git_output.decode(self.encoding)
            if len(git_output) == 0:
                raise EnvironmentError('could not get commit author for rev')
            return git_output
        d.addCallback(process)
        return d