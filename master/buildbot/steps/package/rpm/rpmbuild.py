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
# Portions Copyright Buildbot Team Members

from __future__ import with_statement
# Portions Copyright Dan Radez <dradez+buildbot@redhat.com>
# Portions Copyright Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com>

import os
from buildbot.steps.shell import ShellCommand
from buildbot.process import buildstep

class RpmBuild(ShellCommand):
    name = "rpmbuilder"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["RPMBUILD"]
    descriptionDone = ["RPMBUILD"]

    def __init__(self,
                 specfile=None,
                 topdir='`pwd`',
                 builddir='`pwd`',
                 rpmdir='`pwd`',
                 sourcedir='`pwd`',
                 specdir='`pwd`',
                 srcrpmdir='`pwd`',
                 dist='.el5',
                 autoRelease=False,
                 vcsRevision=False,
                 **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.rpmbuild = (
            'rpmbuild --define "_topdir %s" --define "_builddir %s"'
            ' --define "_rpmdir %s" --define "_sourcedir %s"'
            ' --define "_specdir %s" --define "_srcrpmdir %s"'
            ' --define "dist %s"' % (topdir, builddir, rpmdir, sourcedir,
            specdir, srcrpmdir, dist))
        self.specfile = specfile
        self.autoRelease = autoRelease
        self.vcsRevision = vcsRevision

    def start(self):
        if self.autoRelease:
            relfile = '%s.release' % (
                os.path.basename(self.specfile).split('.')[0])
            try:
                with open(relfile, 'r') as rfile:
                    rel = int(rfile.readline().strip())
            except:
                rel = 0
            self.rpmbuild = self.rpmbuild + ' --define "_release %s"' % rel
            with open(relfile, 'w') as rfile:
                rfile.write(str(rel+1))

        if self.vcsRevision:
            self.rpmbuild = self.rpmbuild + ' --define "_revision %s"' % \
                self.getProperty('got_revision')

        self.rpmbuild = self.rpmbuild + ' -ba %s' % self.specfile

        self.command = self.rpmbuild

        # create the actual RemoteShellCommand instance now
        kwargs = self.remote_kwargs
        kwargs['command'] = self.command
        cmd = buildstep.RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)
        self.startCommand(cmd)

    def createSummary(self, log):
        rpm_prefixes = ['Provides:', 'Requires(rpmlib):', 'Requires:',
                        'Checking for unpackaged', 'Wrote:',
                        'Executing(%', '+ ']
        rpm_err_pfx = ['   ', 'RPM build errors:', 'error: ']

        rpmcmdlog = []
        rpmerrors = []

        for line in log.readlines():
            for pfx in rpm_prefixes:
                if pfx in line:
                    rpmcmdlog.append(line)
            for err in rpm_err_pfx:
                if err in line:
                    rpmerrors.append(line)
        self.addCompleteLog('RPM Command Log', "".join(rpmcmdlog))
        self.addCompleteLog('RPM Errors', "".join(rpmerrors))
