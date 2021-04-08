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

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process import logobserver
from buildbot.process import remotecommand
from buildbot.process import results
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
    basetgz = None
    _default_basetgz = "/var/cache/pbuilder/{distribution}-{architecture}-buildbot.tgz"
    mirror = "http://cdn.debian.net/debian/"
    extrapackages = []
    keyring = None
    components = None

    maxAge = 60 * 60 * 24 * 7
    pbuilder = '/usr/sbin/pbuilder'
    baseOption = '--basetgz'

    renderables = ['architecture', 'distribution', 'basetgz', 'mirror', 'extrapackages', 'keyring',
                   'components']

    def __init__(self,
                 architecture=None,
                 distribution=None,
                 basetgz=None,
                 mirror=None,
                 extrapackages=None,
                 keyring=None,
                 components=None,
                 **kwargs):
        super().__init__(**kwargs)

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
        if basetgz:
            self.basetgz = basetgz

        if not self.distribution:
            config.error("You must specify a distribution.")

        self.suppressions.append(
            (None, re.compile(r"\.pbuilderrc does not exist"), None, None))

        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    @defer.inlineCallbacks
    def run(self):
        if self.basetgz is None:
            self.basetgz = self._default_basetgz
            kwargs = {}
            if self.architecture:
                kwargs['architecture'] = self.architecture
            else:
                kwargs['architecture'] = 'local'
            kwargs['distribution'] = self.distribution
            self.basetgz = self.basetgz.format(**kwargs)

        self.command = ['pdebuild', '--buildresult', '.', '--pbuilder', self.pbuilder]
        if self.architecture:
            self.command += ['--architecture', self.architecture]
        self.command += ['--', '--buildresult', '.', self.baseOption, self.basetgz]
        if self.extrapackages:
            self.command += ['--extrapackages', " ".join(self.extrapackages)]

        res = yield self.checkBasetgz()
        if res != results.SUCCESS:
            return res

        res = yield super().run()
        return res

    @defer.inlineCallbacks
    def checkBasetgz(self):
        cmd = remotecommand.RemoteCommand('stat', {'file': self.basetgz})
        yield self.runCommand(cmd)

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
                command += ['--debootstrapopts', "--keyring={}".format(self.keyring)]
            if self.components:
                command += ['--components', self.components]

            cmd = remotecommand.RemoteShellCommand(self.workdir, command)

            stdio_log = yield self.addLog("pbuilder")
            cmd.useLog(stdio_log, True, "stdio")

            self.description = ["PBuilder", "create."]
            yield self.updateSummary()

            yield self.runCommand(cmd)
            if cmd.rc != 0:
                log.msg("Failure when running {}.".format(cmd))
                return results.FAILURE
            return results.SUCCESS

        s = cmd.updates["stat"][-1]
        # basetgz will be a file when running in pbuilder
        # and a directory in case of cowbuilder
        if stat.S_ISREG(s[stat.ST_MODE]) or stat.S_ISDIR(s[stat.ST_MODE]):
            log.msg("{} found.".format(self.basetgz))
            age = time.time() - s[stat.ST_MTIME]
            if age >= self.maxAge:
                log.msg("basetgz outdated, updating")
                command = ['sudo', self.pbuilder, '--update',
                           self.baseOption, self.basetgz]

                cmd = remotecommand.RemoteShellCommand(self.workdir, command)
                stdio_log = yield self.addLog("pbuilder")
                cmd.useLog(stdio_log, True, "stdio")

                yield self.runCommand(cmd)
                if cmd.rc != 0:
                    log.msg("Failure when running {}.".format(cmd))
                    return results.FAILURE
            return results.SUCCESS

        log.msg("{} is not a file or a directory.".format(self.basetgz))
        return results.FAILURE

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

    _default_basetgz = "/var/cache/pbuilder/{distribution}-{architecture}-buildbot.cow/"

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
