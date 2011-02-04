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

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess


class Darcs(SourceBaseCommand):
    """Darcs-specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['repourl'] (required): the Darcs repository string
    """

    header = "darcs operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
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
        darcs = self.getCommand('darcs')
        assert not self.revision
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [darcs, 'pull', '--all', '--verbose']
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        darcs = self.getCommand('darcs')
        # checkout or export
        d = self.builder.basedir
        command = [darcs, 'get', '--verbose', '--partial',
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
        darcs = self.getCommand('darcs')

        # we use 'darcs context' to find out what we wound up with
        command = [darcs, "changes", "--context"]
        c = runprocess.RunProcess(self.builder, command,
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env, timeout=self.timeout,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        d.addCallback(lambda res: c.stdout)
        return d
