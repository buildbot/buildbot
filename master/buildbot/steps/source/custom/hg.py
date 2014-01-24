#### Mercurial command
from buildbot.steps.source.mercurial import Mercurial
from twisted.internet import defer
import os
from twisted.python import log
from buildbot.changes.changes import Change

class Hg(Mercurial):

    def __init__(self, **kwargs):
        Mercurial.__init__(self, **kwargs)

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
        lastRev = yield self.master.db.sourcestamps.findLastBuildRev(self.build.builder.name, self.codebase, self.repourl, self.update_branch)

        currentRev  = sourcestamps_updated[self.codebase]

        if lastRev is None or lastRev == '' or lastRev == currentRev:
            revrange = '%s:%s' % (currentRev, currentRev)
        else:
            rev= yield self._dovccmd(['log', '-r', lastRev,  r'--template={rev}'], collectStdout=True)
            revrange =  '%d:%s' % ((int(rev.strip())+1), currentRev)

        # build from latest will have empty rev
        command = ['log', '-b', self.update_branch, '-r', revrange,  r'--template={rev}:{node}\n'
                   ]
        stdout= yield self._dovccmd(command, collectStdout=True)

        revNodeList = [rn.split(':', 1) for rn in stdout.strip().split()]

        changelist = []
        for rev, node in reversed(revNodeList):
            timestamp, author, comments = yield self._getRevDetails(
                node)

            changelist.append(Change(who=author, files=None, comments=comments, when=timestamp, repository=self.repourl, branch=self.update_branch, revision=node, codebase= self.codebase))

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

    def _getRevDetails(self, rev):
        """Return a deferred for (date, author, files, comments) of given rev.
        Deferred will be in error if rev is unknown.
        """
        args = ['log', '-r', rev, r'--template={date|hgdate}\n{author}\n{desc|strip}']

        # Mercurial fails with status 255 if rev is unknown
        d = self._dovccmd(args, collectStdout=True)

        def process(output):
            # fortunately, Mercurial issues all filenames one one line
            date, author, comments = output.decode('utf-8', "replace").split(
                os.linesep, 2)

            try:
                stamp = float(date.split()[0])
            except:
                log.msg('hg: caught exception converting output %r '
                        'to timestamp' % date)
                raise

            return stamp, author.strip(), comments.strip()

        d.addCallback(process)
        return d