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

# Visual studio steps

from __future__ import absolute_import
from __future__ import print_function

import re

from buildbot import config
from buildbot.process.buildstep import LogLineObserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps.shell import ShellCommand


def addEnvPath(env, name, value):
    """ concat a path for this name """
    try:
        oldval = env[name]
        if not oldval.endswith(';'):
            oldval = oldval + ';'
    except KeyError:
        oldval = ""
    if not value.endswith(';'):
        value = value + ';'
    env[name] = oldval + value


class MSLogLineObserver(LogLineObserver):

    stdoutDelimiter = "\r\n"
    stderrDelimiter = "\r\n"

    _re_delimiter = re.compile(r'^(\d+>)?-{5}.+-{5}$')
    _re_file = re.compile(r'^(\d+>)?[^ ]+\.(cpp|c)$')
    _re_warning = re.compile(r' ?: warning [A-Z]+[0-9]+:')
    _re_error = re.compile(r' ?error ([A-Z]+[0-9]+)?\s?: ')

    nbFiles = 0
    nbProjects = 0
    nbWarnings = 0
    nbErrors = 0

    logwarnings = None
    logerrors = None

    def __init__(self, logwarnings, logerrors, **kwargs):
        LogLineObserver.__init__(self, **kwargs)
        self.logwarnings = logwarnings
        self.logerrors = logerrors

    def outLineReceived(self, line):
        if self._re_delimiter.search(line):
            self.nbProjects += 1
            self.logwarnings.addStdout("%s\n" % line)
            self.logerrors.addStdout("%s\n" % line)
            self.step.setProgress('projects', self.nbProjects)
        elif self._re_file.search(line):
            self.nbFiles += 1
            self.step.setProgress('files', self.nbFiles)
        elif self._re_warning.search(line):
            self.nbWarnings += 1
            self.logwarnings.addStdout("%s\n" % line)
            self.step.setProgress('warnings', self.nbWarnings)
        elif self._re_error.search("%s\n" % line):
            # error has no progress indication
            self.nbErrors += 1
            self.logerrors.addStderr("%s\n" % line)


class VisualStudio(ShellCommand):
    # an *abstract* base class, which will not itself work as a buildstep

    name = "compile"
    description = "compiling"
    descriptionDone = "compile"

    progressMetrics = (ShellCommand.progressMetrics +
                       ('projects', 'files', 'warnings',))

    logobserver = None

    installdir = None
    default_installdir = None

    # One of build, or rebuild
    mode = "rebuild"

    projectfile = None
    config = None
    useenv = False
    project = None
    PATH = []
    INCLUDE = []
    LIB = []

    renderables = ['projectfile', 'config', 'project', 'mode']

    def __init__(self,
                 installdir=None,
                 mode="rebuild",
                 projectfile=None,
                 config='release',
                 useenv=False,
                 project=None,
                 INCLUDE=None,
                 LIB=None,
                 PATH=None,
                 **kwargs):
        if INCLUDE is None:
            INCLUDE = []
        if LIB is None:
            LIB = []
        if PATH is None:
            PATH = []
        self.installdir = installdir
        self.mode = mode
        self.projectfile = projectfile
        self.config = config
        self.useenv = useenv
        self.project = project
        if INCLUDE:
            self.INCLUDE = INCLUDE
            self.useenv = True
        if LIB:
            self.LIB = LIB
            self.useenv = True
        if PATH:
            self.PATH = PATH
        # always upcall !
        ShellCommand.__init__(self, **kwargs)

    def setupLogfiles(self, cmd, logfiles):
        logwarnings = self.addLog("warnings")
        logerrors = self.addLog("errors")
        self.logobserver = MSLogLineObserver(logwarnings, logerrors)
        self.addLogObserver('stdio', self.logobserver)
        ShellCommand.setupLogfiles(self, cmd, logfiles)

    def setupInstalldir(self):
        if not self.installdir:
            self.installdir = self.default_installdir

    def setupEnvironment(self, cmd):
        ShellCommand.setupEnvironment(self, cmd)
        if cmd.args['env'] is None:
            cmd.args['env'] = {}

        # setup the custom one, those one goes first
        for path in self.PATH:
            addEnvPath(cmd.args['env'], "PATH", path)
        for path in self.INCLUDE:
            addEnvPath(cmd.args['env'], "INCLUDE", path)
        for path in self.LIB:
            addEnvPath(cmd.args['env'], "LIB", path)

        self.setupInstalldir()

    def describe(self, done=False):
        description = ShellCommand.describe(self, done)
        if done:
            if not description:
                description = ['compile']
            description.append(
                '%d projects' % self.getStatistic('projects', 0))
            description.append('%d files' % self.getStatistic('files', 0))
            warnings = self.getStatistic('warnings', 0)
            if warnings > 0:
                description.append('%d warnings' % warnings)
            errors = self.getStatistic('errors', 0)
            if errors > 0:
                description.append('%d errors' % errors)
        return description

    def createSummary(self, log):
        self.setStatistic('projects', self.logobserver.nbProjects)
        self.setStatistic('files', self.logobserver.nbFiles)
        self.setStatistic('warnings', self.logobserver.nbWarnings)
        self.setStatistic('errors', self.logobserver.nbErrors)

    def evaluateCommand(self, cmd):
        if cmd.didFail():
            return FAILURE
        if self.logobserver.nbErrors > 0:
            return FAILURE
        if self.logobserver.nbWarnings > 0:
            return WARNINGS
        return SUCCESS

    def finished(self, result):
        self.getLog("warnings").finish()
        self.getLog("errors").finish()
        ShellCommand.finished(self, result)


class VC6(VisualStudio):

    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio'

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)

        # Root of Visual Developer Studio Common files.
        VSCommonDir = self.installdir + '\\Common'
        MSVCDir = self.installdir + '\\VC98'
        MSDevDir = VSCommonDir + '\\msdev98'

        addEnvPath(cmd.args['env'], "PATH", MSDevDir + '\\BIN')
        addEnvPath(cmd.args['env'], "PATH", MSVCDir + '\\BIN')
        addEnvPath(cmd.args['env'], "PATH", VSCommonDir + '\\TOOLS\\WINNT')
        addEnvPath(cmd.args['env'], "PATH", VSCommonDir + '\\TOOLS')

        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\INCLUDE')
        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\ATL\\INCLUDE')
        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\MFC\\INCLUDE')

        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\LIB')
        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\MFC\\LIB')

    def start(self):
        command = [
            "msdev",
            self.projectfile,
            "/MAKE"
        ]
        if self.project is not None:
            command.append(self.project + " - " + self.config)
        else:
            command.append("ALL - " + self.config)
        if self.mode == "rebuild":
            command.append("/REBUILD")
        elif self.mode == "clean":
            command.append("/CLEAN")
        else:
            command.append("/BUILD")
        if self.useenv:
            command.append("/USEENV")
        self.setCommand(command)
        return VisualStudio.start(self)


class VC7(VisualStudio):
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio .NET 2003'

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)

        VSInstallDir = self.installdir + '\\Common7\\IDE'
        VCInstallDir = self.installdir
        MSVCDir = self.installdir + '\\VC7'

        addEnvPath(cmd.args['env'], "PATH", VSInstallDir)
        addEnvPath(cmd.args['env'], "PATH", MSVCDir + '\\BIN')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\Common7\\Tools')
        addEnvPath(
            cmd.args['env'], "PATH", VCInstallDir + '\\Common7\\Tools\\bin')

        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\INCLUDE')
        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\ATLMFC\\INCLUDE')
        addEnvPath(
            cmd.args['env'], "INCLUDE", MSVCDir + '\\PlatformSDK\\include')
        addEnvPath(
            cmd.args['env'], "INCLUDE", VCInstallDir + '\\SDK\\v1.1\\include')

        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\LIB')
        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\ATLMFC\\LIB')
        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\PlatformSDK\\lib')
        addEnvPath(cmd.args['env'], "LIB", VCInstallDir + '\\SDK\\v1.1\\lib')

    def start(self):
        command = [
            "devenv.com",
            self.projectfile
        ]
        if self.mode == "rebuild":
            command.append("/Rebuild")
        elif self.mode == "clean":
            command.append("/Clean")
        else:
            command.append("/Build")
        command.append(self.config)
        if self.useenv:
            command.append("/UseEnv")
        if self.project is not None:
            command.append("/Project")
            command.append(self.project)
        self.setCommand(command)
        return VisualStudio.start(self)


# alias VC7 as VS2003
VS2003 = VC7


class VC8(VC7):

    # Our ones
    arch = None
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio 8'

    renderables = ['arch']

    def __init__(self, arch="x86", **kwargs):
        self.arch = arch

        # always upcall !
        VisualStudio.__init__(self, **kwargs)

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)

        VSInstallDir = self.installdir
        VCInstallDir = self.installdir + '\\VC'

        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\Common7\\IDE')
        if self.arch == "x64":
            addEnvPath(
                cmd.args['env'], "PATH", VCInstallDir + '\\BIN\\x86_amd64')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\BIN')
        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\Common7\\Tools')
        addEnvPath(
            cmd.args['env'], "PATH", VSInstallDir + '\\Common7\\Tools\\bin')
        addEnvPath(
            cmd.args['env'], "PATH", VCInstallDir + '\\PlatformSDK\\bin')
        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\SDK\\v2.0\\bin')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\VCPackages')
        addEnvPath(cmd.args['env'], "PATH", r'${PATH}')

        addEnvPath(cmd.args['env'], "INCLUDE", VCInstallDir + '\\INCLUDE')
        addEnvPath(
            cmd.args['env'], "INCLUDE", VCInstallDir + '\\ATLMFC\\include')
        addEnvPath(
            cmd.args['env'], "INCLUDE", VCInstallDir + '\\PlatformSDK\\include')

        archsuffix = ''
        if self.arch == "x64":
            archsuffix = '\\amd64'
        addEnvPath(cmd.args['env'], "LIB", VCInstallDir + '\\LIB' + archsuffix)
        addEnvPath(
            cmd.args['env'], "LIB", VCInstallDir + '\\ATLMFC\\LIB' + archsuffix)
        addEnvPath(
            cmd.args['env'], "LIB", VCInstallDir + '\\PlatformSDK\\lib' + archsuffix)
        addEnvPath(
            cmd.args['env'], "LIB", VSInstallDir + '\\SDK\\v2.0\\lib' + archsuffix)


# alias VC8 as VS2005
VS2005 = VC8


class VCExpress9(VC8):

    def start(self):
        command = [
            "vcexpress",
            self.projectfile
        ]
        if self.mode == "rebuild":
            command.append("/Rebuild")
        elif self.mode == "clean":
            command.append("/Clean")
        else:
            command.append("/Build")
        command.append(self.config)
        if self.useenv:
            command.append("/UseEnv")
        if self.project is not None:
            command.append("/Project")
            command.append(self.project)
        self.setCommand(command)
        return VisualStudio.start(self)


# Add first support for VC9 (Same as VC8, with a different installdir)
class VC9(VC8):
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio 9.0'


VS2008 = VC9


# VC10 doesn't look like it needs extra stuff.
class VC10(VC9):
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio 10.0'


VS2010 = VC10


# VC11 doesn't look like it needs extra stuff.
class VC11(VC10):
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio 11.0'


VS2012 = VC11


# VC12 doesn't look like it needs extra stuff.
class VC12(VC11):
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio 12.0'


VS2013 = VC12


# VC14 doesn't look like it needs extra stuff.
class VC14(VC12):
    default_installdir = 'C:\\Program Files (x86)\\Microsoft Visual Studio 14.0'


VS2015 = VC14


class MsBuild4(VisualStudio):
    platform = None
    vcenv_bat = r"${VS110COMNTOOLS}..\..\VC\vcvarsall.bat"
    renderables = ['platform']

    def __init__(self, platform, **kwargs):
        self.platform = platform
        VisualStudio.__init__(self, **kwargs)

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)
        cmd.args['env']['VCENV_BAT'] = self.vcenv_bat

    def describe(self, done=False):
        rv = []
        if done:
            rv.append("built")
        else:
            rv.append("building")
        if self.project is not None:
            rv.append("%s for" % (self.project))
        else:
            rv.append("solution for")
        rv.append("%s|%s" % (self.config, self.platform))
        return rv

    def start(self):
        if self.platform is None:
            config.error(
                'platform is mandatory. Please specify a string such as "Win32"')

        command = ('"%%VCENV_BAT%%" x86 && msbuild "%s" /p:Configuration="%s" /p:Platform="%s" /maxcpucount'
                   % (self.projectfile, self.config, self.platform))

        if self.project is not None:
            command += ' /t:"%s"' % (self.project)
        elif self.mode == "build":
            command += ' /t:Build'
        elif self.mode == "clean":
            command += ' /t:Clean'
        elif self.mode == "rebuild":
            command += ' /t:Rebuild'

        self.setCommand(command)

        return VisualStudio.start(self)


MsBuild = MsBuild4


class MsBuild12(MsBuild4):
    vcenv_bat = r"${VS120COMNTOOLS}..\..\VC\vcvarsall.bat"


class MsBuild14(MsBuild4):
    vcenv_bat = r"${VS140COMNTOOLS}..\..\VC\vcvarsall.bat"
