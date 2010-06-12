import os

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands import utils


class Darcs(SourceBaseCommand):
    """Darcs-specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['repourl'] (required): the Darcs repository string
    """

    header = "darcs operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.vcexe = utils.getCommand("darcs")
        self.repourl = args['repourl']
        self.sourcedata = "%s\n" % self.repourl
        self.revision = self.args.get('revision')

    def sourcedirIsUpdateable(self):
        # checking out a specific revision requires a full 'darcs get'
        return (not self.revision and
                not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, "_darcs")))

    def doVCUpdate(self):
        assert not self.revision
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'pull', '--all', '--verbose']
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        # checkout or export
        d = self.builder.basedir
        command = [self.vcexe, 'get', '--verbose', '--partial',
                   '--repo-name', self.srcdir]
        if self.revision:
            # write the context to a file
            n = os.path.join(self.builder.basedir, ".darcs-context")
            f = open(n, "wb")
            f.write(self.revision)
            f.close()
            # tell Darcs to use that context
            command.append('--context')
            command.append(n)
        command.append(self.repourl)

        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        if self.revision:
            d.addCallback(self.removeContextFile, n)
        return d

    def removeContextFile(self, res, n):
        os.unlink(n)
        return res

    def parseGotRevision(self):
        # we use 'darcs context' to find out what we wound up with
        command = [self.vcexe, "changes", "--context"]
        c = runprocess.RunProcess(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env, timeout=self.timeout,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        d.addCallback(lambda res: c.stdout)
        return d
