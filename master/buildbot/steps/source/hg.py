#### Mercurial command
from buildbot.steps.source.mercurial import Mercurial
from twisted.internet import defer

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

        # calculate rev ranges

        print "\n parseChanges parameters %s,%s,%s,%s\n" %  (self.branch, self.update_branch, self.revision, self.repourl)
        # build from latest will have empty rev
        command = ['log', '-b', self.update_branch, '-r', "0:17",  r'--template={rev}:{node}\n'
                   ]
        stdout= yield self._dovccmd(command, collectStdout=True)

        print "\n results %s\n" % stdout.strip()
        defer.returnValue(0)

