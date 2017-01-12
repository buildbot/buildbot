# This program is free software; you can
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
# Portions Copyright Marius Rieder <marius.rieder@durchmesser.ch>
"""
Steps and objects related to pbuilder
"""

from __future__ import absolute_import
from __future__ import print_function

import re
import stat
import time

from twisted.python import log

from buildbot import config
from buildbot.process import logobserver
from buildbot.process import remotecommand
from buildbot.process.buildstep import FAILURE
from buildbot.steps.shell import WarningCountingShellCommand


class DebPbuilder(WarningCountingShellCommand):

    """Build a debian package with pbuilder inside of a chroot."""
    name = "pbuilder"

    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["building"]
    descriptionDone = ["built"]

    warningPattern = r".*(warning[: ]|\sW: ).*"

    architecture = None
    distribution = 'stable'
    basetgz = "/var/cache/pbuilder/%(distribution)s-%(architecture)s-buildbot.tgz"
    mirror = "http://cdn.debian.net/debian/"
    extrapackages = []
    keyring = None
    components = None

    maxAge = 60 * 60 * 24 * 7
    pbuilder = '/usr/sbin/pbuilder'
    baseOption = '--basetgz'

    def __init__(self,
                 architecture=None,
                 distribution=None,
                 basetgz=None,
                 mirror=None,
                 extrapackages=None,
                 keyring=None,
                 components=None,
                 **kwargs):
        """
        Creates the DebPbuilder object.

        @type architecture: str
        @param architecture: the name of the architecture to build
        @type distribution: str
        @param distribution: the man of the distribution to use
        @type basetgz: str
        @param basetgz: the path or  path template of the basetgz
        @type mirror: str
        @param mirror: the mirror for building basetgz
        @type extrapackages: list
        @param extrapackages: adds packages specified to buildroot
        @type keyring: str
        @param keyring: keyring file to use for verification
        @type components: str
        @param components: components to use for chroot creation
        @type kwargs: dict
        @param kwargs: All further keyword arguments.
        """
        WarningCountingShellCommand.__init__(self, **kwargs)

        if architecture:
            self.architecture = architecture
        if distribution:
            self.distribution = distribution
        if mirror:
            self.mirror = mirror
        if extrapackages:
            self.extrapackages = extrapackages
        if keyring:
            self.keyring = keyring
        if components:
            self.components = components

        if self.architecture:
            kwargs['architecture'] = self.architecture
        else:
            kwargs['architecture'] = 'local'
        kwargs['distribution'] = self.distribution

        if basetgz:
            self.basetgz = basetgz % kwargs
        else:
            self.basetgz = self.basetgz % kwargs

        if not self.distribution:
            config.error("You must specify a distribution.")

        self.command = [
            'pdebuild', '--buildresult', '.', '--pbuilder', self.pbuilder]
        if self.architecture:
            self.command += ['--architecture', self.architecture]
        self.command += ['--', '--buildresult',
                         '.', self.baseOption, self.basetgz]
        if self.extrapackages:
            self.command += ['--extrapackages', " ".join(self.extrapackages)]

        self.suppressions.append(
            (None, re.compile(r"\.pbuilderrc does not exist"), None, None))

        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    # Check for Basetgz
    def start(self):
        cmd = remotecommand.RemoteCommand('stat', {'file': self.basetgz})
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.checkBasetgz(cmd))
        d.addErrback(self.failed)
        return d

    def checkBasetgz(self, cmd):
        if cmd.rc != 0:
            log.msg("basetgz not found, initializing it.")

            command = ['sudo', self.pbuilder, '--create', self.baseOption,
                       self.basetgz, '--distribution', self.distribution,
                       '--mirror', self.mirror]
            if self.architecture:
                command += ['--architecture', self.architecture]
            if self.extrapackages:
                command += ['--extrapackages', " ".join(self.extrapackages)]
            if self.keyring:
                command += ['--debootstrapopts', "--keyring=%s" % self.keyring]
            if self.components:
                command += ['--components', self.components]

            cmd = remotecommand.RemoteShellCommand(self.workdir, command)

            stdio_log = stdio_log = self.addLog("pbuilder")
            cmd.useLog(stdio_log, True, "stdio")
            d = self.runCommand(cmd)
            self.step_status.setText(["PBuilder create."])
            d.addCallback(lambda res: self.startBuild(cmd))
            return d
        s = cmd.updates["stat"][-1]
        # basetgz will be a file when running in pbuilder
        # and a directory in case of cowbuilder
        if stat.S_ISREG(s[stat.ST_MODE]) or stat.S_ISDIR(s[stat.ST_MODE]):
            log.msg("%s found." % self.basetgz)
            age = time.time() - s[stat.ST_MTIME]
            if age >= self.maxAge:
                log.msg("basetgz outdated, updating")
                command = ['sudo', self.pbuilder, '--update',
                           self.baseOption, self.basetgz]

                cmd = remotecommand.RemoteShellCommand(self.workdir, command)
                stdio_log = stdio_log = self.addLog("pbuilder")
                cmd.useLog(stdio_log, True, "stdio")
                d = self.runCommand(cmd)
                d.addCallback(lambda res: self.startBuild(cmd))
                return d
            return self.startBuild(cmd)
        else:
            log.msg("%s is not a file or a directory." % self.basetgz)
            self.finished(FAILURE)

    def startBuild(self, cmd):
        if cmd.rc != 0:
            log.msg("Failure when running %s." % cmd)
            self.finished(FAILURE)
        else:
            return WarningCountingShellCommand.start(self)

    def logConsumer(self):
        r = re.compile(r"dpkg-genchanges  >\.\./(.+\.changes)")
        while True:
            stream, line = yield
            mo = r.search(line)
            if mo:
                self.setProperty("deb-changes", mo.group(1), "DebPbuilder")


class DebCowbuilder(DebPbuilder):

    """Build a debian package with cowbuilder inside of a chroot."""
    name = "cowbuilder"

    basetgz = "/var/cache/pbuilder/%(distribution)s-%(architecture)s-buildbot.cow/"

    pbuilder = '/usr/sbin/cowbuilder'
    baseOption = '--basepath'


class UbuPbuilder(DebPbuilder):

    """Build a Ubuntu package with pbuilder inside of a chroot."""
    distribution = None
    mirror = "http://archive.ubuntu.com/ubuntu/"

    components = "main universe"


class UbuCowbuilder(DebCowbuilder):

    """Build a Ubuntu package with cowbuilder inside of a chroot."""
    distribution = None
    mirror = "http://archive.ubuntu.com/ubuntu/"

    components = "main universe"
