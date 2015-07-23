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
# Portions Copyright Dan Radez <dradez+buildbot@redhat.com>
# Portions Copyright Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com>
import os

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.steps.shell import ShellCommand


class RpmBuild(ShellCommand):

    """
    RpmBuild build step.
    """

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
        """
        Create the RpmBuild object.

        @type specfile: str
        @param specfile: location of the specfile to build
        @type topdir: str
        @param topdir: define the _topdir rpm parameter
        @type builddir: str
        @param builddir: define the _builddir rpm parameter
        @type rpmdir: str
        @param rpmdir: define the _rpmdir rpm parameter
        @type sourcedir: str
        @param sourcedir: define the _sourcedir rpm parameter
        @type specdir: str
        @param specdir: define the _specdir rpm parameter
        @type srcrpmdir: str
        @param srcrpmdir: define the _srcrpmdir rpm parameter
        @type dist: str
        @param dist: define the dist string.
        @type autoRelease: boolean
        @param autoRelease: Use auto incrementing release numbers.
        @type vcsRevision: boolean
        @param vcsRevision: Use vcs version number as revision number.
        """
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

        if not self.specfile:
            config.error("You must specify a specfile")

        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    def start(self):
        if self.autoRelease:
            relfile = '%s.release' % (
                os.path.basename(self.specfile).split('.')[0])
            try:
                with open(relfile, 'r') as rfile:
                    rel = int(rfile.readline().strip())
            except (IOError, TypeError, ValueError):
                rel = 0
            self.rpmbuild = self.rpmbuild + ' --define "_release %s"' % rel
            with open(relfile, 'w') as rfile:
                rfile.write(str(rel + 1))

        if self.vcsRevision:
            revision = self.getProperty('got_revision')
            # only do this in the case where there's a single codebase
            if revision and not isinstance(revision, dict):
                self.rpmbuild = (self.rpmbuild + ' --define "_revision %s"' %
                                 revision)

        self.rpmbuild = self.rpmbuild + ' -ba %s' % self.specfile

        self.command = self.rpmbuild

        # create the actual RemoteShellCommand instance now
        kwargs = self.remote_kwargs
        kwargs['command'] = self.command
        kwargs['workdir'] = self.workdir
        cmd = buildstep.RemoteShellCommand(**kwargs)
        self.setupEnvironment(cmd)
        self.startCommand(cmd)
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    def logConsumer(self):
        rpm_prefixes = ['Provides:', 'Requires(', 'Requires:',
                        'Checking for unpackaged', 'Wrote:',
                        'Executing(%', '+ ', 'Processing files:']
        rpm_err_pfx = ['   ', 'RPM build errors:', 'error: ']
        self.rpmcmdlog = []
        self.rpmerrors = []

        while True:
            stream, line = yield
            for pfx in rpm_prefixes:
                if line.startswith(pfx):
                    self.rpmcmdlog.append(line)
                    break
            for err in rpm_err_pfx:
                if line.startswith(err):
                    self.rpmerrors.append(line)
                    break

    def createSummary(self, log):
        self.addCompleteLog('RPM Command Log', "".join(self.rpmcmdlog))
        if self.rpmerrors:
            self.addCompleteLog('RPM Errors', "".join(self.rpmerrors))
