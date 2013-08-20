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
    def full(self):
        if self.method == 'clobber':
            yield self.clobber(None)
            return

        updatable = yield self._sourcedirIsUpdatable()
        # the below fixes the case when cloning a new repository and selecting a specific rev/named branch
        command = ['clone', self.repourl]
        if not updatable:
            # clone to specific revision / branch
            if self.revision:
                command += ['--rev', self.revision]
            elif self.branchType == 'inrepo':
                command += ['--rev', self.update_branch]
            command += "."
            yield self._dovccmd(command)
        ##
        elif self.method == 'clean':
            yield self.clean(None)
        elif self.method == 'fresh':
            yield self.fresh(None)
        else:
            raise ValueError("Unknown method, check your configuration")

    @defer.inlineCallbacks
    def parseChanges(self, _):
        self.master = self.build.builder.botmaster.parent

        sourcestamps_updated = self.build.build_status.getAllGotRevisions()
        # calculate rev ranges
        lastRev = yield self.master.db.sourcestamps.findLastBuildRev(self.build.builder.name, self.codebase, self.repourl, self.update_branch)

        currentRev  = sourcestamps_updated[self.codebase]

        if lastRev is None or lastRev == '' or lastRev == currentRev:
            revrange = '%s:%s' % (currentRev, currentRev)
        else:
            rev= yield self._dovccmd(['log', '-r', lastRev,  r'--template={rev}'], collectStdout=True)
            revrange =  '%d:%s' % (int(rev.strip()), currentRev)

        # build from latest will have empty rev
        command = ['log', '-b', self.update_branch, '-r', revrange,  r'--template={rev}:{node}\n'
                   ]
        stdout= yield self._dovccmd(command, collectStdout=True)

        revNodeList = [rn.split(':', 1) for rn in stdout.strip().split()]

        changelist = []
        for rev, node in revNodeList:
            timestamp, author, files, comments = yield self._getRevDetails(
                node)

            changelist.append(Change(who=author, files=files, comments=comments, when=timestamp, repository=self.repourl, revision=rev, codebase= self.codebase))

        sourcestamps = self.build.build_status.getSourceStamps()


        for ss in sourcestamps:
            if ss.codebase == self.codebase:
                ss.changes = changelist
                ss.revision = sourcestamps_updated[self.codebase]
                break

        if len(sourcestamps_updated) > 0:
            ss = [{'b_codebase': self.codebase, 'b_revision': sourcestamps_updated[self.codebase], 'b_sourcestampsetid': sourcestamps[0].sourcestampsetid}]
            result = yield self.master.db.sourcestamps.updateSourceStamps(ss)

        defer.returnValue(0)

    def _getRevDetails(self, rev):
        """Return a deferred for (date, author, files, comments) of given rev.
        Deferred will be in error if rev is unknown.
        """
        args = ['log', '-r', rev, r'--template={date|hgdate}\n{author}\n{files}\n{desc|strip}']

        # Mercurial fails with status 255 if rev is unknown
        d = self._dovccmd(args, collectStdout=True)

        def process(output):
            # fortunately, Mercurial issues all filenames one one line
            date, author, files, comments = output.decode('utf-8', "replace").split(
                os.linesep, 3)

            try:
                stamp = float(date.split()[0])
            except:
                log.msg('hg: caught exception converting output %r '
                        'to timestamp' % date)
                raise

            return stamp, author.strip(), files.split(), comments.strip()

        d.addCallback(process)
        return d