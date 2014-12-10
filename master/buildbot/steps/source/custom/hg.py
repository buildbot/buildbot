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
    def pullLastRev(self, lastRev):
            command = ['pull' , self.repourl]
            rev = ['--rev', lastRev]
            if self.update_branch:
                rev = ['--rev', self.update_branch]

            command.extend(rev)
            yield self._dovccmd(command)

    @defer.inlineCallbacks
    def parseChanges(self, _):
        sourcestamps_updated = self.build.build_status.getAllGotRevisions()

        buildLatestRev = self.build.getProperty("buildLatestRev", False)
        if type(buildLatestRev) != bool:
            buildLatestRev = (buildLatestRev.lower() == "true")

        if buildLatestRev == False:
            self.updateBuildSourceStamps(sourcestamps_updated)
            defer.returnValue(0)

        self.master = self.build.builder.botmaster.parent

        # calculate rev ranges
        lastRev = yield self.master.db.sourcestamps.findLastBuildRev(self.build.builder.name,
                                                                     self.build.requests[0].id,
                                                                     self.codebase,
                                                                     self.repourl,
                                                                     self.update_branch)

        currentRev  = sourcestamps_updated[self.codebase]

        if lastRev is None or lastRev == '' or lastRev == currentRev:
            revrange = '%s:%s' % (currentRev, currentRev)
        else:
            yield self.pullLastRev(lastRev)

            rev= yield self._dovccmd(['log', '-r', lastRev,  r'--template={rev}'], collectStdout=True)
            revrange =  '%d:%s' % ((int(rev.strip())), currentRev)

        # build from latest will have empty rev
        command = ['log', '-b', self.update_branch, '-r', revrange,  r'--template={rev}:{node}\n'
                   ]
        stdout= yield self._dovccmd(command, collectStdout=True)

        revNodeList = [rn.split(':', 1) for rn in stdout.strip().split()]

        changelist = []
        for rev, node in reversed(revNodeList):
            if (node == lastRev) and (lastRev != currentRev):
                continue
            timestamp, author, comments = yield self._getRevDetails(
                node)

            changelist.append(Change(who=author, files=None, comments=comments, when=timestamp,
                                     repository=self.repourl, branch=self.update_branch, revision=node,
                                     codebase= self.codebase))

        self.updateBuildSourceStamps(sourcestamps_updated, changelist)

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
            try:
                date, author, comments = output.decode('utf-8', "replace").split(
                    os.linesep, 2)
            except:
                date, author, comments = output.decode('utf-8', "replace").split(
                    "\n", 2)

            try:
                stamp = float(date.split()[0])
            except:
                log.msg('hg: caught exception converting output %r '
                        'to timestamp' % date)
                raise

            return stamp, author.strip(), comments.strip()

        d.addCallback(process)
        return d