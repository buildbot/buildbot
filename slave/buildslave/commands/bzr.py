# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os

from twisted.python import log
from twisted.internet import defer

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess


class Bzr(SourceBaseCommand):
    """bzr-specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['repourl'] (required): the Bzr repository string
    ['forceSharedRepo']: force this to a shared repo
    """

    header = "bzr operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.repourl = args['repourl']
        self.sourcedata = "%s\n" % self.repourl
        self.revision = self.args.get('revision')
        self.forceSharedRepo = args.get('forceSharedRepo')

    def sourcedirIsUpdateable(self):
        # checking out a specific revision requires a full 'bzr checkout'
        return (not self.revision and
                not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, ".bzr")))

    def start(self):
        def cont(res):
            # Continue with start() method in superclass.
            return SourceBaseCommand.start(self)

        if self.forceSharedRepo:
            d = self.doForceSharedRepo();
            d.addCallback(cont)
            return d
        else:
            return cont(None)

    def doVCUpdate(self):
        bzr = self.getCommand('bzr')
        assert not self.revision
        # update: possible for mode in ('copy', 'update')
        srcdir = os.path.join(self.builder.basedir, self.srcdir)
        command = [bzr, 'update']
        c = runprocess.RunProcess(self.builder, command, srcdir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        bzr = self.getCommand('bzr')

        # checkout or export
        d = self.builder.basedir
        if self.mode == "export":
            # exporting in bzr requires a separate directory
            return self.doVCExport()
        # originally I added --lightweight here, but then 'bzr revno' is
        # wrong. The revno reported in 'bzr version-info' is correct,
        # however. Maybe this is a bzr bug?
        #
        # In addition, you cannot perform a 'bzr update' on a repo pulled
        # from an HTTP repository that used 'bzr checkout --lightweight'. You
        # get a "ERROR: Cannot lock: transport is read only" when you try.
        #
        # So I won't bother using --lightweight for now.

        command = [bzr, 'checkout']
        if self.revision:
            command.append('--revision')
            command.append(str(self.revision))
        command.append(self.repourl)
        command.append(self.srcdir)

        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        return d

    def doVCExport(self):
        bzr = self.getCommand('bzr')
        tmpdir = os.path.join(self.builder.basedir, "export-temp")
        srcdir = os.path.join(self.builder.basedir, self.srcdir)
        command = [bzr, 'checkout', '--lightweight']
        if self.revision:
            command.append('--revision')
            command.append(str(self.revision))
        command.append(self.repourl)
        command.append(tmpdir)
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        def _export(res):
            command = [bzr, 'export', srcdir]
            c = runprocess.RunProcess(self.builder, command, tmpdir,
                             sendRC=False, timeout=self.timeout,
                             maxTime=self.maxTime, usePTY=False)
            self.command = c
            return c.start()
        d.addCallback(_export)
        return d

    def doForceSharedRepo(self):
        bzr = self.getCommand('bzr')

        # Don't send stderr. When there is no shared repo, this might confuse
        # users, as they will see a bzr error message. But having no shared
        # repo is not an error, just an indication that we need to make one.
        c = runprocess.RunProcess(self.builder, [bzr, 'info', '.'],
                         self.builder.basedir,
                         sendStderr=False, sendRC=False, usePTY=False)
        d = c.start()
        def afterCheckSharedRepo(res):
            if type(res) is int and res != 0:
                log.msg("No shared repo found, creating it")
                # bzr info fails, try to create shared repo.
                c = runprocess.RunProcess(self.builder, [bzr, 'init-repo', '.'],
                                 self.builder.basedir,
                                 sendRC=False, usePTY=False)
                self.command = c
                return c.start()
            else:
                return defer.succeed(res)
        d.addCallback(afterCheckSharedRepo)
        return d

    def get_revision_number(self, out):
        # it feels like 'bzr revno' sometimes gives different results than
        # the 'revno:' line from 'bzr version-info', and the one from
        # version-info is more likely to be correct.
        for line in out.split("\n"):
            colon = line.find(":")
            if colon != -1:
                key, value = line[:colon], line[colon+2:]
                if key == "revno":
                    return int(value)
        raise ValueError("unable to find revno: in bzr output: '%s'" % out)

    def parseGotRevision(self):
        bzr = self.getCommand('bzr')
        command = [bzr, "version-info"]
        c = runprocess.RunProcess(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            try:
                return self.get_revision_number(c.stdout)
            except ValueError:
                msg =("Bzr.parseGotRevision unable to parse output "
                      "of bzr version-info: '%s'" % c.stdout.strip())
                log.msg(msg)
                self.sendStatus({'header': msg + "\n"})
                return None
        d.addCallback(_parse)
        return d

