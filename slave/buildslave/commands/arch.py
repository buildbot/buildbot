import os

from twisted.python import log

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands import utils


class Arch(SourceBaseCommand):
    """Arch-specific (tla-specific) VC operation. In addition to the
    arguments handled by SourceBaseCommand, this command reads the following keys:

    ['url'] (required): the repository string
    ['version'] (required): which version (i.e. branch) to retrieve
    ['revision'] (optional): the 'patch-NN' argument to check out
    ['archive']: the archive name to use. If None, use the archive's default
    ['build-config']: if present, give to 'tla build-config' after checkout
    """

    header = "arch operation"
    buildconfig = None

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.vcexe = utils.getCommand("tla")
        self.archive = args.get('archive')
        self.url = args['url']
        self.version = args['version']
        self.revision = args.get('revision')
        self.buildconfig = args.get('build-config')
        self.sourcedata = "%s\n%s\n%s\n" % (self.url, self.version,
                                            self.buildconfig)

    def sourcedirIsUpdateable(self):
        # Arch cannot roll a directory backwards, so if they ask for a
        # specific revision, clobber the directory. Technically this
        # could be limited to the cases where the requested revision is
        # later than our current one, but it's too hard to extract the
        # current revision from the tree.
        return (not self.revision and
                not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, "{arch}")))

    def doVCUpdate(self):
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'replay']
        if self.revision:
            command.append(self.revision)
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        # to do a checkout, we must first "register" the archive by giving
        # the URL to tla, which will go to the repository at that URL and
        # figure out the archive name. tla will tell you the archive name
        # when it is done, and all further actions must refer to this name.

        command = [self.vcexe, 'register-archive', '--force', self.url]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, keepStdout=True, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(self._didRegister, c)
        return d

    def _didRegister(self, res, c):
        # find out what tla thinks the archive name is. If the user told us
        # to use something specific, make sure it matches.
        r = re.search(r'Registering archive: (\S+)\s*$', c.stdout)
        if r:
            msg = "tla reports archive name is '%s'" % r.group(1)
            log.msg(msg)
            self.builder.sendUpdate({'header': msg+"\n"})
            if self.archive and r.group(1) != self.archive:
                msg = (" mismatch, we wanted an archive named '%s'"
                       % self.archive)
                log.msg(msg)
                self.builder.sendUpdate({'header': msg+"\n"})
                raise AbandonChain(-1)
            self.archive = r.group(1)
        assert self.archive, "need archive name to continue"
        return self._doGet()

    def _doGet(self):
        ver = self.version
        if self.revision:
            ver += "--%s" % self.revision
        command = [self.vcexe, 'get', '--archive', self.archive,
                   '--no-pristine',
                   ver, self.srcdir]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        if self.buildconfig:
            d.addCallback(self._didGet)
        return d

    def _didGet(self, res):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.vcexe, 'build-config', self.buildconfig]
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d

    def parseGotRevision(self):
        # using code from tryclient.TlaExtractor
        # 'tla logs --full' gives us ARCHIVE/BRANCH--REVISION
        # 'tla logs' gives us REVISION
        command = [self.vcexe, "logs", "--full", "--reverse"]
        c = runprocess.RunProcess(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            tid = c.stdout.split("\n")[0].strip()
            slash = tid.index("/")
            dd = tid.rindex("--")
            #branch = tid[slash+1:dd]
            baserev = tid[dd+2:]
            return baserev
        d.addCallback(_parse)
        return d


class Bazaar(Arch):
    """Bazaar (/usr/bin/baz) is an alternative client for Arch repositories.
    It is mostly option-compatible, but archive registration is different
    enough to warrant a separate Command.

    ['archive'] (required): the name of the archive being used
    """

    def setup(self, args):
        Arch.setup(self, args)
        self.vcexe = utils.getCommand("baz")
        # baz doesn't emit the repository name after registration (and
        # grepping through the output of 'baz archives' is too hard), so we
        # require that the buildmaster configuration to provide both the
        # archive name and the URL.
        self.archive = args['archive'] # required for Baz
        self.sourcedata = "%s\n%s\n%s\n" % (self.url, self.version,
                                            self.buildconfig)

    # in _didRegister, the regexp won't match, so we'll stick with the name
    # in self.archive

    def _doGet(self):
        # baz prefers ARCHIVE/VERSION. This will work even if
        # my-default-archive is not set.
        ver = self.archive + "/" + self.version
        if self.revision:
            ver += "--%s" % self.revision
        command = [self.vcexe, 'get', '--no-pristine',
                   ver, self.srcdir]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        if self.buildconfig:
            d.addCallback(self._didGet)
        return d

    def parseGotRevision(self):
        # using code from tryclient.BazExtractor
        command = [self.vcexe, "tree-id"]
        c = runprocess.RunProcess(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            tid = c.stdout.strip()
            slash = tid.index("/")
            dd = tid.rindex("--")
            #branch = tid[slash+1:dd]
            baserev = tid[dd+2:]
            return baserev
        d.addCallback(_parse)
        return d


