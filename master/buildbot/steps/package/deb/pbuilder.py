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

import re
import stat
import time

from twisted.python import log

from buildbot.steps.shell import WarningCountingShellCommand
from buildbot.process import buildstep
from buildbot.process.properties import WithProperties

class DebPbuilder(WarningCountingShellCommand):
    """Build a debian package with pbuilder inside of a chroot."""
    name = "pbuilder"

    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["pdebuilding"]
    descriptionDone = ["pdebuild"]

    warningPattern = ".*(warning[: ]|\sW: ).*"

    architecture = None
    distribution = 'stable'
    basetgz = "/var/cache/pbuilder/%(distribution)s-%(architecture)s-buildbot.tgz"
    mirror = "http://cdn.debian.net/debian/"
    extrapackages = []

    maxAge = 60*60*24*7

    def __init__(self,
                 architecture=None,
                 distribution=None,
                 basetgz=None,
                 mirror=None,
		 extrapackages=None,
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
        
        if self.architecture:
            kwargs['architecture'] = self.architecture
        else:
            kwargs['architecture'] = 'ownarch'
        kwargs['distribution'] = self.distribution

        if basetgz:
            self.basetgz = basetgz % kwargs
        else:
            self.basetgz = self.basetgz % kwargs

        if extrapackages:
            self.extrapackages = extrapackages
            
        self.command = ['pdebuild', '--buildresult', '.']
        if self.architecture:
            self.command += ['--architecture', self.architecture]
        self.command += ['--', '--buildresult', '.', '--basetgz', self.basetgz]
        if self.extrapackages:
            self.command += ['--extrapackages', " ".join(self.extrapackages)]

        self.suppressions.append((None, re.compile("\.pbuilderrc does not exist"), None, None))

    # Check for Basetgz
    def start(self):
        cmd = buildstep.RemoteCommand('stat', {'file': self.basetgz})
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.checkBasetgz(cmd))
        d.addErrback(self.failed)
        return d

    def checkBasetgz(self, cmd):
        if cmd.rc != 0:
            log.msg("basetgz not found, initializing it.")

            command = ['sudo', '/usr/sbin/pbuilder', '--create', '--basetgz',
                       self.basetgz, '--distribution', self.distribution,
                       '--mirror', self.mirror]
            if self.architecture:
                command += ['--architecture', self.architecture]
            if self.extrapackages:
                command += ['--extrapackages', " ".join(self.extrapackages)]

            cmd = buildstep.RemoteShellCommand(self.getWorkdir(), command)
            
            stdio_log = stdio_log = self.addLog("pbuilder")
            cmd.useLog(stdio_log, True, "stdio")
            d = self.runCommand(cmd)
            self.step_status.setText(["PBuilder create."])
            d.addCallback(lambda res: self.startBuild(cmd))
            return d
        s = cmd.updates["stat"][-1]
        if stat.S_ISREG(s[stat.ST_MODE]):
            log.msg("%s found." % self.basetgz)
            age = time.time() - s[stat.ST_MTIME]
            if age >= self.maxAge:
                log.msg("basetgz outdated, updating")
                command = ['sudo', '/usr/sbin/pbuilder', '--update', '--basetgz', self.basetgz]
            
                cmd = buildstep.RemoteShellCommand(self.getWorkdir(), command)
                stdio_log = stdio_log = self.addLog("pbuilder")
                cmd.useLog(stdio_log, True, "stdio")
                d = self.runCommand(cmd)
                self.step_status.setText(["PBuilder update."])
                d.addCallback(lambda res: self.startBuild(cmd))
                return d
            return self.startBuild(cmd)
        else:
            log.msg("%s is not a file." % self.basetgz)
            self.finished(FAILURE)
        
    def startBuild(self, dummy):
        return WarningCountingShellCommand.start(self)

    def commandComplete(self, cmd):
    	out = cmd.logs['stdio'].getText()
        m = re.search(r"dpkg-genchanges  >\.\./(.+\.changes)", out)
        if m:
            self.setProperty("deb-changes", m.group(1), "DebPbuilder")

