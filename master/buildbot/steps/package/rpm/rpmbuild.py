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

from twisted.internet import defer

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver


class RpmBuild(buildstep.ShellMixin, buildstep.BuildStep):

    """
    RpmBuild build step.
    """

    renderables = ['dist']
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
                 dist='.el6',
                 define=None,
                 autoRelease=False,
                 vcsRevision=False,
                 **kwargs):
        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super().__init__(**kwargs)

        self.dist = dist

        self.base_rpmbuild = (
            ('rpmbuild --define "_topdir {}" --define "_builddir {}"'
             ' --define "_rpmdir {}" --define "_sourcedir {}"'
             ' --define "_specdir {}" --define "_srcrpmdir {}"').format(topdir, builddir, rpmdir,
                                                                        sourcedir, specdir,
                                                                        srcrpmdir))

        if define is None:
            define = {}
        for k, v in define.items():
            self.base_rpmbuild += " --define \"{} {}\"".format(k, v)

        self.specfile = specfile
        self.autoRelease = autoRelease
        self.vcsRevision = vcsRevision

        if not self.specfile:
            config.error("You must specify a specfile")

        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    @defer.inlineCallbacks
    def run(self):

        rpm_extras_dict = {}
        rpm_extras_dict['dist'] = self.dist

        if self.autoRelease:
            relfile = '{}.release'.format(os.path.basename(self.specfile).split('.')[0])
            try:
                with open(relfile, 'r') as rfile:
                    rel = int(rfile.readline().strip())
            except (IOError, TypeError, ValueError):
                rel = 0
            rpm_extras_dict['_release'] = rel
            with open(relfile, 'w') as rfile:
                rfile.write(str(rel + 1))

        if self.vcsRevision:
            revision = self.getProperty('got_revision')
            # only do this in the case where there's a single codebase
            if revision and not isinstance(revision, dict):
                rpm_extras_dict['_revision'] = revision

        self.rpmbuild = self.base_rpmbuild

        # The unit tests expect a certain order, so we sort the dict to keep
        # format the same every time
        for k, v in sorted(rpm_extras_dict.items()):
            self.rpmbuild = '{0} --define "{1} {2}"'.format(
                self.rpmbuild, k, v)

        command = '{} -ba {}'.format(self.rpmbuild, self.specfile)

        cmd = yield self.makeRemoteShellCommand(command=command)

        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        yield self.addCompleteLog('RPM Command Log', "\n".join(self.rpmcmdlog))
        if self.rpmerrors:
            yield self.addCompleteLog('RPM Errors', "\n".join(self.rpmerrors))

        return cmd.results()

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
