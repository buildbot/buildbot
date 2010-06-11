import os

from twisted.python import log

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands import utils


class BK(SourceBaseCommand):
    """BitKeeper-specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['bkurl'] (required): the BK repository string
    """

    header = "bk operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.vcexe = utils.getCommand("bk")
        self.bkurl = args['bkurl']
        self.sourcedata = '"%s\n"' % self.bkurl

        self.bk_args = []
        if args.get('extra_args', None) is not None:
            self.bk_args.extend(args['extra_args'])

    def sourcedirIsUpdateable(self):
        if os.path.exists(os.path.join(self.builder.basedir,
                                       self.srcdir, ".buildbot-patched")):
            return False
        return os.path.isfile(os.path.join(self.builder.basedir,
                                          self.srcdir, "BK/parent"))

    def doVCUpdate(self):
        revision = self.args['revision'] or 'HEAD'
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)

        # Revision is ignored since the BK free client doesn't support it.
        command = [self.vcexe, 'pull']
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):

        revision_arg = ''
        if self.args['revision']:
            revision_arg = "-r%s" % self.args['revision']

        d = self.builder.basedir

        command = [self.vcexe, 'clone', revision_arg] + self.bk_args + \
                   [self.bkurl, self.srcdir]
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True, usePTY=False)
        self.command = c
        return c.start()

    def getBKVersionCommand(self):
        """
        Get the (shell) command used to determine BK revision number
        of checked-out code

        return: list of strings, passable as the command argument to RunProcess
        """
        return [self.vcexe, "changes", "-r+", "-d:REV:"]

    def parseGotRevision(self):
        c = runprocess.RunProcess(self.builder,
                         self.getBKVersionCommand(),
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            r_raw = c.stdout.strip()
            got_version = None
            try:
                r = r_raw
            except:
                msg = ("BK.parseGotRevision unable to parse output: (%s)" % r_raw)
                log.msg(msg)
                self.sendStatus({'header': msg + "\n"})
                raise ValueError(msg)
            return r
        d.addCallback(_parse)
        return d




