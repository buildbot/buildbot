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
import time

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess

class CVS(SourceBaseCommand):
    """CVS-specific VC operation. In addition to the arguments handled by
    SourceBaseCommand, this command reads the following keys:

    ['cvsroot'] (required): the CVSROOT repository string
    ['cvsmodule'] (required): the module to be retrieved
    ['branch']: a '-r' tag or branch name to use for the checkout/update
    ['login']: a string for use as a password to 'cvs login'
    ['global_options']: a list of strings to use before the CVS verb
    ['checkout_options']: a list of strings to use after checkout,
                          but before revision and branch specifiers
    ['checkout_options']: a list of strings to use after export,
                          but before revision and branch specifiers
    ['extra_options']: a list of strings to use after export and checkout,
                          but before revision and branch specifiers
    """

    header = "cvs operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.cvsroot = args['cvsroot']
        self.cvsmodule = args['cvsmodule']
        self.global_options = args.get('global_options', [])
        self.checkout_options = args.get('checkout_options', [])
        self.export_options = args.get('export_options', [])
        self.extra_options = args.get('extra_options', [])
        self.branch = args.get('branch')
        self.login = args.get('login')
        self.sourcedata = "%s\n%s\n%s\n" % (self.cvsroot, self.cvsmodule,
                                            self.branch)

    def sourcedirIsUpdateable(self):
        return (not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir, "CVS")))

    def start(self):
        cvs = self.getCommand("cvs")
        if self.login is not None:
            # need to do a 'cvs login' command first
            d = self.builder.basedir
            command = ([cvs, '-d', self.cvsroot] + self.global_options
                       + ['login'])
            c = runprocess.RunProcess(self.builder, command, d,
                             sendRC=False, timeout=self.timeout,
                             maxTime=self.maxTime,
                             initialStdin=self.login+"\n", usePTY=False)
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)
            d.addCallback(self._didLogin)
            return d
        else:
            return self._didLogin(None)

    def _didLogin(self, res):
        # now we really start
        return SourceBaseCommand.start(self)

    def doVCUpdate(self):
        cvs = self.getCommand("cvs")
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [cvs, '-z3'] + self.global_options + ['update', '-dP']
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCFull(self):
        cvs = self.getCommand("cvs")
        d = self.builder.basedir
        if self.mode == "export":
            verb = "export"
        else:
            verb = "checkout"
        command = ([cvs, '-d', self.cvsroot, '-z3'] +
                   self.global_options +
                   [verb, '-d', self.srcdir])

        if verb == "checkout":
            command += self.checkout_options
        else:
            command += self.export_options
        command += self.extra_options

        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        command += [self.cvsmodule]

        c = runprocess.RunProcess(self.builder, command, d,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def parseGotRevision(self):
        # CVS does not have any kind of revision stamp to speak of. We return
        # the current timestamp as a best-effort guess, but this depends upon
        # the local system having a clock that is
        # reasonably-well-synchronized with the repository.
        return time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime())

