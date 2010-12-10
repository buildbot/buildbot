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

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess


class BK(SourceBaseCommand):
    """BitKeeper-specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['bkurl'] (required): the BK repository string
    """

    header = "bk operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
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
        bk = self.getCommand('bk')
        # XXX revision is never used!! - bug #1715
        # revision = self.args['revision'] or 'HEAD'
        # update: possible for mode in ('copy', 'update')
        d = os.path.join(self.builder.basedir, self.srcdir)

        # Revision is ignored since the BK free client doesn't support it.
        command = [bk, 'pull']
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         keepStdout=True, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        bk = self.getCommand('bk')

        revision_arg = ''
        if self.args['revision']:
            revision_arg = "-r%s" % self.args['revision']

        d = self.builder.basedir

        command = [bk, 'clone', revision_arg] + self.bk_args + \
                   [self.bkurl, self.srcdir]
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         usePTY=False)
        self.command = c
        return c.start()

    def getBKVersionCommand(self):
        """
        Get the (shell) command used to determine BK revision number
        of checked-out code

        return: list of strings, passable as the command argument to RunProcess
        """
        bk = self.getCommand('bk')
        return [bk, "changes", "-r+", "-d:REV:"]

    def parseGotRevision(self):
        c = runprocess.RunProcess(self.builder,
                         self.getBKVersionCommand(),
                         os.path.join(self.builder.basedir, self.srcdir),
                         environ=self.env, timeout=self.timeout,
                         sendStdout=False, sendStderr=False, sendRC=False,
                         keepStdout=True, usePTY=False)
        d = c.start()
        def _parse(res):
            r_raw = c.stdout.strip()
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




