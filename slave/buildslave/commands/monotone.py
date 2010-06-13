import os

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.commands import utils


class Monotone(SourceBaseCommand):
    """Monotone-specific VC operation.  In addition to the arguments handled
    by SourceBaseCommand, this command reads the following keys:

    ['server_addr'] (required): the address of the server to pull from
    ['branch'] (required): the branch the revision is on
    ['db_path'] (required): the local database path to use
    ['revision'] (required): the revision to check out (None not allowed)
    ['monotone']: path to monotone executable
    """

    header = "monotone operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.server_addr = args["server_addr"]
        self.branch = args["branch"]
        self.db_path = args["db_path"]
        self.revision = args["revision"]
        self.monotone = args.get("monotone", utils.getCommand('mtn'))
        self._made_fulls = False
        self._pull_timeout = self.timeout

    def _makefulls(self):
        if not self._made_fulls:
            basedir = self.builder.basedir
            self.full_db_path = os.path.join(basedir, self.db_path)
            self.full_srcdir = os.path.join(basedir, self.srcdir)
            self._made_fulls = True

    def sourcedirIsUpdateable(self):
        self._makefulls()
        return (not self.sourcedirIsPatched() and
                os.path.isfile(self.full_db_path) and
                os.path.isdir(os.path.join(self.full_srcdir, "MT")))

    def doVCUpdate(self):
        return self._withFreshDb(self._doUpdate)

    def _doUpdate(self):
        # update: possible for mode in ('copy', 'update')
        command = [self.monotone, "update",
                   "-r", self.revision,
                   "-b", self.branch]
        c = runprocess.RunProcess(self.builder, command, self.srcdir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        return self._withFreshDb(self._doFull)

    def _doFull(self):
        command = [self.monotone, "--db=" + self.full_db_path,
                   "checkout",
                   "-r", self.revision,
                   "-b", self.branch,
                   self.srcdir]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def _withFreshDb(self, callback):
        self._makefulls()
        # first ensure the db exists and is usable
        if os.path.isfile(self.full_db_path):
            # already exists, so run 'db migrate' in case monotone has been
            # upgraded under us
            command = [self.monotone, "db", "migrate",
                       "--db=" + self.full_db_path]
        else:
            # We'll be doing an initial pull, so up the timeout to 3 hours to
            # make sure it will have time to complete.
            self._pull_timeout = max(self._pull_timeout, 3 * 60 * 60)
            self.sendStatus({"header": "creating database %s\n"
                                       % (self.full_db_path,)})
            command = [self.monotone, "db", "init",
                       "--db=" + self.full_db_path]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(self._didDbInit)
        d.addCallback(self._didPull, callback)
        return d

    def _didDbInit(self, res):
        command = [self.monotone, "--db=" + self.full_db_path,
                   "pull", "--ticker=dot", self.server_addr, self.branch]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self._pull_timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.sendStatus({"header": "pulling %s from %s\n"
                                   % (self.branch, self.server_addr)})
        self.command = c
        return c.start()

    def _didPull(self, res, callback):
        return callback()
