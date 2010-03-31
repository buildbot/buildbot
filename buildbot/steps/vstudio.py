# Visual studio steps

from buildbot.steps.shell import ShellCommand
from buildbot.process.buildstep import LogLineObserver
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE

import re

 
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

    _re_delimitor = re.compile(r'^(\d+>)?-{5}.+-{5}$')
    _re_file = re.compile(r'^(\d+>)?[^ ]+\.(cpp|c)$')
    _re_warning = re.compile(r' : warning [A-Z]+[0-9]+:')
    _re_error = re.compile(r' error [A-Z]+[0-9]+\s?: ')

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
        self.stdoutParser.delimiter = "\r\n"
        self.stderrParser.delimiter = "\r\n"

    def outLineReceived(self, line):
        if self._re_delimitor.search(line):
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
            # error is no progres indication
            self.nbErrors += 1
            self.logerrors.addStderr("%s\n" % line)
    

class VisualStudio(ShellCommand):
    name = "compile"
    description = "compiling"
    descriptionDone = "compile"

    logobserver = None

    installdir = None

    # One of build, or rebuild
    mode = "rebuild"

    projectfile = None
    config = None
    useenv = False
    PATH = []
    INCLUDE = []
    LIB = []
    
    def __init__(self, **kwargs):
        # cleanup kwargs
        if 'installdir' in kwargs:
            self.installdir = kwargs['installdir']
            del kwargs['installdir']
        if 'mode' in kwargs:
            self.config = kwargs['mode']
            del kwargs['mode']
        if 'projectfile' in kwargs:
            self.projectfile = kwargs['projectfile']
            del kwargs['projectfile']
        if 'config' in kwargs:
            self.config = kwargs['config']
            del kwargs['config']
        if 'useenv' in kwargs:
            self.useenv = kwargs['useenv']
            del kwargs['useenv']
        # one of those next two forces the usage of env variables
        if 'INCLUDE' in kwargs:
            self.useenv = True
            self.INCLUDE = kwargs['INCLUDE']
            del kwargs['INCLUDE']
        if 'LIB' in kwargs:
            self.useenv = True
            self.LIB = kwargs['LIB']
            del kwargs['LIB']
        if 'PATH' in kwargs:
            self.PATH = kwargs['PATH']
            del kwargs['PATH']            

        # always upcall !
        ShellCommand.__init__(self, **kwargs)

    def setupProgress(self):
        self.progressMetrics += ('projects', 'files', 'warnings',)
        return ShellCommand.setupProgress(self)

    def setupLogfiles(self, cmd, logfiles):
        logwarnings = self.addLog("warnings")
        logerrors = self.addLog("errors")
        self.logobserver = MSLogLineObserver(logwarnings, logerrors)
        self.addLogObserver('stdio', self.logobserver)
        ShellCommand.setupLogfiles(self, cmd, logfiles)


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


    def describe(self, done=False):
        description = ShellCommand.describe(self, done)
        if done:
            description.append('%d projects' % self.step_status.getStatistic('projects', 0))
            description.append('%d files' % self.step_status.getStatistic('files', 0))
            warnings = self.step_status.getStatistic('warnings', 0)
            if warnings > 0:
                description.append('%d warnings' % warnings)
            errors = self.step_status.getStatistic('errors', 0)
            if errors > 0:
                description.append('%d errors' % errors)
        return description

    def createSummary(self, log):
        self.step_status.setStatistic('projects', self.logobserver.nbProjects)
        self.step_status.setStatistic('files', self.logobserver.nbFiles)
        self.step_status.setStatistic('warnings', self.logobserver.nbWarnings)
        self.step_status.setStatistic('errors', self.logobserver.nbErrors)

    def evaluateCommand(self, cmd):
        if self.logobserver.nbErrors > 0:
            return FAILURE
        if self.logobserver.nbWarnings > 0:
            return WARNINGS
        else:
            return SUCCESS

    def finished(self, result):
        self.getLog("warnings").finish()
        self.getLog("errors").finish()
        ShellCommand.finished(self, result)

class VC6(VisualStudio):

    def __init__(self, **kwargs):  

        # always upcall !
        VisualStudio.__init__(self, **kwargs)

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)

        if self.installdir:
            installdir = self.installdir
        else:
            installdir = 'C:\\Program Files\\Microsoft Visual Studio'

        # Root of Visual Developer Studio Common files.
        VSCommonDir = installdir + '\\Common'
        MSVCDir = installdir + '\\VC98'
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
        command = ["msdev"]
        command.append(self.projectfile)
        command.append("/MAKE")
        command.append("ALL - " + self.config)
        if self.mode == "rebuild":
            command.append("/REBUILD")
        else:
            command.append("/BUILD")
        if self.useenv:
            command.append("/USEENV")
        self.setCommand(command)
        return VisualStudio.start(self)    

class VC7(VisualStudio):

    def __init__(self, **kwargs):  

        # always upcall !
        VisualStudio.__init__(self, **kwargs)

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)

        if self.installdir:
            installdir = self.installdir
        else:
            installdir = 'C:\\Program Files\\Microsoft Visual Studio .NET 2003'
        
        VSInstallDir = installdir + '\\Common7\\IDE'
        VCInstallDir = installdir
        MSVCDir = installdir + '\\VC7'

        addEnvPath(cmd.args['env'], "PATH", VSInstallDir)
        addEnvPath(cmd.args['env'], "PATH", MSVCDir + '\\BIN')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\Common7\\Tools')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\Common7\\Tools\\bin')

        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\INCLUDE')
        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\ATLMFC\\INCLUDE')
        addEnvPath(cmd.args['env'], "INCLUDE", MSVCDir + '\\PlatformSDK\\include')
        addEnvPath(cmd.args['env'], "INCLUDE", VCInstallDir + '\\SDK\\v1.1\\include')

        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\LIB')
        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\ATLMFC\\LIB')
        addEnvPath(cmd.args['env'], "LIB", MSVCDir + '\\PlatformSDK\\lib')
        addEnvPath(cmd.args['env'], "LIB", VCInstallDir + '\\SDK\\v1.1\\lib')
        
    def start(self):
        command = ["devenv"]
        command.append(self.projectfile)
        if self.mode == "rebuild":
            command.append("/Rebuild")
        else:
            command.append("/Build")
        command.append(self.config)
        if self.useenv:
            command.append("/UseEnv")
        self.setCommand(command)
        return VisualStudio.start(self)

#alias VC7 as VS2003
VS2003 = VC7

class VC8(VisualStudio):
    
    # Our ones
    arch = "x86"

    def __init__(self, **kwargs):

        # cleanup kwargs
        if 'arch' in kwargs:
            self.arch = kwargs['arch']
            del kwargs['arch']

        # always upcall !
        VisualStudio.__init__(self, **kwargs)

    def setupEnvironment(self, cmd):
        VisualStudio.setupEnvironment(self, cmd)

        if self.installdir:
            installdir = self.installdir
        else:
            installdir = 'C:\\Program Files\\Microsoft Visual Studio 8'

        VSInstallDir = installdir
        VCInstallDir = installdir + '\\VC'

        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\Common7\\IDE')
        if self.arch == "x64":
            addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\BIN\\x86_amd64')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\BIN')
        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\Common7\\Tools')
        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\Common7\\Tools\\bin')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\PlatformSDK\\bin')
        addEnvPath(cmd.args['env'], "PATH", VSInstallDir + '\\SDK\\v2.0\\bin')
        addEnvPath(cmd.args['env'], "PATH", VCInstallDir + '\\VCPackages')
        addEnvPath(cmd.args['env'], "PATH", r'${PATH}')

        addEnvPath(cmd.args['env'], "INCLUDE", VCInstallDir + '\\INCLUDE')
        addEnvPath(cmd.args['env'], "INCLUDE", VCInstallDir + '\\ATLMFC\\include')
        addEnvPath(cmd.args['env'], "INCLUDE", VCInstallDir + '\\PlatformSDK\\include')

        archsuffix = ''
        if self.arch == "x64":
            archsuffix = '\\amd64'
        addEnvPath(cmd.args['env'], "LIB", VCInstallDir + '\\LIB' + archsuffix)
        addEnvPath(cmd.args['env'], "LIB", VCInstallDir + '\\ATLMFC\\LIB' + archsuffix)
        addEnvPath(cmd.args['env'], "LIB", VCInstallDir + '\\PlatformSDK\\lib' + archsuffix)
        addEnvPath(cmd.args['env'], "LIB", VSInstallDir + '\\SDK\\v2.0\\lib' + archsuffix)

    # the start method is the same as for VC7
    def start(self):
        command = ["devenv"]
        command.append(self.projectfile)
        if self.mode == "rebuild":
            command.append("/Rebuild")
        else:
            command.append("/Build")
        command.append(self.config)
        if self.useenv:
            command.append("/UseEnv")
        self.setCommand(command)
        return VisualStudio.start(self)

#alias VC8 as VS2005
VS2005 = VC8
