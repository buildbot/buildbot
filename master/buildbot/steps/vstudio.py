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


import re

from twisted.internet import defer

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import results
from buildbot.process.logobserver import LogLineObserver


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
        super().__init__(**kwargs)
        self.logwarnings = logwarnings
        self.logerrors = logerrors

    def outLineReceived(self, line):
        if self._re_delimiter.search(line):
            self.nbProjects += 1
            self.logwarnings.addStdout(f"{line}\n")
            self.logerrors.addStdout(f"{line}\n")
            self.step.setProgress('projects', self.nbProjects)
        elif self._re_file.search(line):
            self.nbFiles += 1
            self.step.setProgress('files', self.nbFiles)
        elif self._re_warning.search(line):
            self.nbWarnings += 1
            self.logwarnings.addStdout(f"{line}\n")
            self.step.setProgress('warnings', self.nbWarnings)
        elif self._re_error.search(f"{line}\n"):
            # error has no progress indication
            self.nbErrors += 1
            self.logerrors.addStderr(f"{line}\n")


class VisualStudio(buildstep.ShellMixin, buildstep.BuildStep):
    # an *abstract* base class, which will not itself work as a buildstep

    name = "compile"
    description = "compiling"
    descriptionDone = "compile"

    progressMetrics = (buildstep.BuildStep.progressMetrics +
                       ('projects', 'files', 'warnings',))

    logobserver = None

    installdir = None
    default_installdir = None

    # One of build, clean or rebuild
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

        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super().__init__(**kwargs)

    def add_env_path(self, name, value):
        """ concat a path for this name """
        try:
            oldval = self.env[name]
            if not oldval.endswith(';'):
                oldval = oldval + ';'
        except KeyError:
            oldval = ""
        if not value.endswith(';'):
            value = value + ';'
        self.env[name] = oldval + value

    @defer.inlineCallbacks
    def setup_log_files(self):
        logwarnings = yield self.addLog("warnings")
        logerrors = yield self.addLog("errors")
        self.logobserver = MSLogLineObserver(logwarnings, logerrors)
        yield self.addLogObserver('stdio', self.logobserver)

    def setupEnvironment(self):
        if self.env is None:
            self.env = {}

        # setup the custom one, those one goes first
        for path in self.PATH:
            self.add_env_path("PATH", path)
        for path in self.INCLUDE:
            self.add_env_path("INCLUDE", path)
        for path in self.LIB:
            self.add_env_path("LIB", path)

        if not self.installdir:
            self.installdir = self.default_installdir

    def evaluate_result(self, cmd):
        self.setStatistic('projects', self.logobserver.nbProjects)
        self.setStatistic('files', self.logobserver.nbFiles)
        self.setStatistic('warnings', self.logobserver.nbWarnings)
        self.setStatistic('errors', self.logobserver.nbErrors)

        if cmd.didFail():
            return results.FAILURE
        if self.logobserver.nbErrors > 0:
            return results.FAILURE
        if self.logobserver.nbWarnings > 0:
            return results.WARNINGS
        return results.SUCCESS

    @defer.inlineCallbacks
    def run(self):
        self.setupEnvironment()
        yield self.setup_log_files()

        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        yield self.finish_logs()
        self.results = self.evaluate_result(cmd)
        return self.results

    def getResultSummary(self):
        if self.logobserver is None:
            # step was skipped or log observer was not created due to another reason
            return {"step": results.Results[self.results]}

        description = (f'compile {self.logobserver.nbProjects} projects {self.logobserver.nbFiles} '
                       'files')

        if self.logobserver.nbWarnings > 0:
            description += f' {self.logobserver.nbWarnings} warnings'
        if self.logobserver.nbErrors > 0:
            description += f' {self.logobserver.nbErrors} errors'

        if self.results != results.SUCCESS:
            description += f' ({results.Results[self.results]})'

        return {'step': description}

    @defer.inlineCallbacks
    def finish_logs(self):
        log = yield self.getLog("warnings")
        yield log.finish()
        log = yield self.getLog("errors")
        yield log.finish()


class VC6(VisualStudio):

    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio'

    def setupEnvironment(self):
        super().setupEnvironment()

        # Root of Visual Developer Studio Common files.
        VSCommonDir = self.installdir + '\\Common'
        MSVCDir = self.installdir + '\\VC98'
        MSDevDir = VSCommonDir + '\\msdev98'

        self.add_env_path("PATH", MSDevDir + '\\BIN')
        self.add_env_path("PATH", MSVCDir + '\\BIN')
        self.add_env_path("PATH", VSCommonDir + '\\TOOLS\\WINNT')
        self.add_env_path("PATH", VSCommonDir + '\\TOOLS')

        self.add_env_path("INCLUDE", MSVCDir + '\\INCLUDE')
        self.add_env_path("INCLUDE", MSVCDir + '\\ATL\\INCLUDE')
        self.add_env_path("INCLUDE", MSVCDir + '\\MFC\\INCLUDE')

        self.add_env_path("LIB", MSVCDir + '\\LIB')
        self.add_env_path("LIB", MSVCDir + '\\MFC\\LIB')

    @defer.inlineCallbacks
    def run(self):
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
        self.command = command

        res = yield super().run()
        return res


class VC7(VisualStudio):
    default_installdir = 'C:\\Program Files\\Microsoft Visual Studio .NET 2003'

    def setupEnvironment(self):
        super().setupEnvironment()

        VSInstallDir = self.installdir + '\\Common7\\IDE'
        VCInstallDir = self.installdir
        MSVCDir = self.installdir + '\\VC7'

        self.add_env_path("PATH", VSInstallDir)
        self.add_env_path("PATH", MSVCDir + '\\BIN')
        self.add_env_path("PATH", VCInstallDir + '\\Common7\\Tools')
        self.add_env_path("PATH", VCInstallDir + '\\Common7\\Tools\\bin')

        self.add_env_path("INCLUDE", MSVCDir + '\\INCLUDE')
        self.add_env_path("INCLUDE", MSVCDir + '\\ATLMFC\\INCLUDE')
        self.add_env_path("INCLUDE", MSVCDir + '\\PlatformSDK\\include')
        self.add_env_path("INCLUDE", VCInstallDir + '\\SDK\\v1.1\\include')

        self.add_env_path("LIB", MSVCDir + '\\LIB')
        self.add_env_path("LIB", MSVCDir + '\\ATLMFC\\LIB')
        self.add_env_path("LIB", MSVCDir + '\\PlatformSDK\\lib')
        self.add_env_path("LIB", VCInstallDir + '\\SDK\\v1.1\\lib')

    @defer.inlineCallbacks
    def run(self):
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
        self.command = command

        res = yield super().run()
        return res


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
        super().__init__(**kwargs)

    def setupEnvironment(self):
        # Do not use super() here. We want to override VC7.setupEnvironment().
        VisualStudio.setupEnvironment(self)

        VSInstallDir = self.installdir
        VCInstallDir = self.installdir + '\\VC'

        self.add_env_path("PATH", VSInstallDir + '\\Common7\\IDE')
        if self.arch == "x64":
            self.add_env_path("PATH", VCInstallDir + '\\BIN\\x86_amd64')
        self.add_env_path("PATH", VCInstallDir + '\\BIN')
        self.add_env_path("PATH", VSInstallDir + '\\Common7\\Tools')
        self.add_env_path("PATH", VSInstallDir + '\\Common7\\Tools\\bin')
        self.add_env_path("PATH", VCInstallDir + '\\PlatformSDK\\bin')
        self.add_env_path("PATH", VSInstallDir + '\\SDK\\v2.0\\bin')
        self.add_env_path("PATH", VCInstallDir + '\\VCPackages')
        self.add_env_path("PATH", r'${PATH}')

        self.add_env_path("INCLUDE", VCInstallDir + '\\INCLUDE')
        self.add_env_path("INCLUDE", VCInstallDir + '\\ATLMFC\\include')
        self.add_env_path("INCLUDE", VCInstallDir + '\\PlatformSDK\\include')

        archsuffix = ''
        if self.arch == "x64":
            archsuffix = '\\amd64'
        self.add_env_path("LIB", VCInstallDir + '\\LIB' + archsuffix)
        self.add_env_path("LIB", VCInstallDir + '\\ATLMFC\\LIB' + archsuffix)
        self.add_env_path("LIB", VCInstallDir + '\\PlatformSDK\\lib' + archsuffix)
        self.add_env_path("LIB", VSInstallDir + '\\SDK\\v2.0\\lib' + archsuffix)


# alias VC8 as VS2005
VS2005 = VC8


class VCExpress9(VC8):

    @defer.inlineCallbacks
    def run(self):
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
        self.command = command

        # Do not use super() here. We want to override VC7.start().
        res = yield VisualStudio.run(self)
        return res


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


class VC141(VC14):
    default_installdir = r"C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\Community"


VS2017 = VC141


class VS2019(VS2017):
    default_installdir = r"C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community"


class VS2022(VS2017):
    default_installdir = r"C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\Community"


def _msbuild_format_defines_parameter(defines):
    if defines is None or len(defines) == 0:
        return ""
    return f' /p:DefineConstants="{";".join(defines)}"'


def _msbuild_format_target_parameter(mode, project):
    modestring = None
    if mode == "clean":
        modestring = 'Clean'
    elif mode == "build":
        modestring = 'Build'
    elif mode == "rebuild":
        modestring = 'Rebuild'

    parameter = ""
    if project is not None:
        if modestring == "Rebuild" or modestring is None:
            parameter = f' /t:"{project}"'
        else:
            parameter = f' /t:"{project}:{modestring}"'
    elif modestring is not None:
        parameter = f' /t:{modestring}'

    return parameter


class MsBuild4(VisualStudio):
    platform = None
    defines = None
    vcenv_bat = r"${VS110COMNTOOLS}..\..\VC\vcvarsall.bat"
    renderables = ['platform']
    description = 'building'

    def __init__(self, platform, defines=None, **kwargs):
        self.platform = platform
        self.defines = defines
        super().__init__(**kwargs)

    def setupEnvironment(self):
        super().setupEnvironment()
        self.env['VCENV_BAT'] = self.vcenv_bat

    def describe_project(self, done=False):
        project = self.project
        if project is None:
            project = 'solution'
        return f'{project} for {self.config}|{self.platform}'

    def getCurrentSummary(self):
        return {'step': 'building ' + self.describe_project()}

    def getResultSummary(self):
        return {'step': 'built ' + self.describe_project()}

    @defer.inlineCallbacks
    def run(self):
        if self.platform is None:
            config.error('platform is mandatory. Please specify a string such as "Win32"')

        yield self.updateSummary()

        command = (f'"%VCENV_BAT%" x86 && msbuild "{self.projectfile}" '
                   f'/p:Configuration="{self.config}" /p:Platform="{self.platform}" /maxcpucount')

        command += _msbuild_format_target_parameter(self.mode, self.project)
        command += _msbuild_format_defines_parameter(self.defines)

        self.command = command

        res = yield super().run()
        return res


MsBuild = MsBuild4


class MsBuild12(MsBuild4):
    vcenv_bat = r"${VS120COMNTOOLS}..\..\VC\vcvarsall.bat"


class MsBuild14(MsBuild4):
    vcenv_bat = r"${VS140COMNTOOLS}..\..\VC\vcvarsall.bat"


class MsBuild141(VisualStudio):
    platform = None
    defines = None
    vcenv_bat = r"\VC\Auxiliary\Build\vcvarsall.bat"
    renderables = ['platform']
    version_range = "[15.0,16.0)"

    def __init__(self, platform, defines=None, **kwargs):
        self.platform = platform
        self.defines = defines
        super().__init__(**kwargs)

    def setupEnvironment(self):
        super().setupEnvironment()
        self.env['VCENV_BAT'] = self.vcenv_bat
        self.add_env_path("PATH",
                   'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\')
        self.add_env_path("PATH",
                   'C:\\Program Files\\Microsoft Visual Studio\\Installer\\')
        self.add_env_path("PATH", r'${PATH}')

    def describe_project(self, done=False):
        project = self.project
        if project is None:
            project = 'solution'
        return f'{project} for {self.config}|{self.platform}'

    @defer.inlineCallbacks
    def run(self):
        if self.platform is None:
            config.error(
                'platform is mandatory. Please specify a string such as "Win32"')

        self.description = 'building ' + self.describe_project()
        self.descriptionDone = 'built ' + self.describe_project()
        yield self.updateSummary()

        command = ('FOR /F "tokens=*" %%I in '
                   f'(\'vswhere.exe -version "{self.version_range}" -products * '
                   '-property installationPath\') '
                   f' do "%%I\\%VCENV_BAT%" x86 && msbuild "{self.projectfile}" '
                   f'/p:Configuration="{self.config}" /p:Platform="{self.platform}" /maxcpucount')

        command += _msbuild_format_target_parameter(self.mode, self.project)
        command += _msbuild_format_defines_parameter(self.defines)

        self.command = command

        res = yield super().run()
        return res


MsBuild15 = MsBuild141


class MsBuild16(MsBuild141):
    version_range = "[16.0,17.0)"


class MsBuild17(MsBuild141):
    version_range = "[17.0,18.0)"
