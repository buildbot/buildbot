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

# N.B.: don't import anything that might pull in a reactor yet. Some of our
# subcommands want to load modules that need the gtk reactor.
import os, sys, re, time
from buildslave.scripts import base
from twisted.python import usage

# the create/start/stop commands should all be run as the same user,
# preferably a separate 'buildbot' account.

# Note that the terms 'options' and 'config' are used interchangeably here - in
# fact, they are interchanged several times.  Caveat legator.

class Maker:
    def __init__(self, config):
        self.config = config
        self.basedir = config['basedir']
        self.force = config.get('force', False)
        self.quiet = config['quiet']

    def mkdir(self):
        if os.path.exists(self.basedir):
            if not self.quiet:
                print "updating existing installation"
            return
        if not self.quiet:
            print "mkdir", self.basedir
        os.mkdir(self.basedir)

    def mkinfo(self):
        path = os.path.join(self.basedir, "info")
        if not os.path.exists(path):
            if not self.quiet:
                print "mkdir", path
            os.mkdir(path)
        created = False
        admin = os.path.join(path, "admin")
        if not os.path.exists(admin):
            if not self.quiet:
                print "Creating info/admin, you need to edit it appropriately"
            f = open(admin, "wt")
            f.write("Your Name Here <admin@youraddress.invalid>\n")
            f.close()
            created = True
        host = os.path.join(path, "host")
        if not os.path.exists(host):
            if not self.quiet:
                print "Creating info/host, you need to edit it appropriately"
            f = open(host, "wt")
            f.write("Please put a description of this build host here\n")
            f.close()
            created = True
        access_uri = os.path.join(path, "access_uri")
        if not os.path.exists(access_uri):
            if not self.quiet:
                print "Not creating info/access_uri - add it if you wish"
        if created and not self.quiet:
            print "Please edit the files in %s appropriately." % path

    def chdir(self):
        if not self.quiet:
            print "chdir", self.basedir
        os.chdir(self.basedir)

    def makeTAC(self, contents, secret=False):
        tacfile = "buildbot.tac"
        if os.path.exists(tacfile):
            oldcontents = open(tacfile, "rt").read()
            if oldcontents == contents:
                if not self.quiet:
                    print "buildbot.tac already exists and is correct"
                return
            if not self.quiet:
                print "not touching existing buildbot.tac"
                print "creating buildbot.tac.new instead"
            tacfile = "buildbot.tac.new"
        f = open(tacfile, "wt")
        f.write(contents)
        f.close()
        if secret:
            os.chmod(tacfile, 0600)

slaveTACTemplate = ["""
import os

from twisted.application import service
from buildslave.bot import BuildSlave

basedir = r'%(basedir)s'
rotateLength = %(log-size)s
maxRotatedFiles = %(log-count)s

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a buildslave
# directory; do not edit it.
application = service.Application('buildslave')
""",
"""
try:
  from twisted.python.logfile import LogFile
  from twisted.python.log import ILogObserver, FileLogObserver
  logfile = LogFile.fromFullPath(os.path.join(basedir, "twistd.log"), rotateLength=rotateLength,
                                 maxRotatedFiles=maxRotatedFiles)
  application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
except ImportError:
  # probably not yet twisted 8.2.0 and beyond, can't set log yet
  pass
""",
"""
buildmaster_host = '%(host)s'
port = %(port)d
slavename = '%(name)s'
passwd = '%(passwd)s'
keepalive = %(keepalive)d
usepty = %(usepty)d
umask = %(umask)s
maxdelay = %(maxdelay)d

s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay,
               allow_shutdown=%(allow-shutdown)s)
s.setServiceParent(application)

"""]

def createSlave(config):
    m = Maker(config)
    m.mkdir()
    m.chdir()
    if config['relocatable']:
        config['basedir'] = '.'
    try:
        master = config['master']
        port = None
        host, port = re.search(r'^([^:]+)(?:[:](\d+))?', master).groups()
        if port == None:
            port = '9989'
        config['host'] = host
        config['port'] = int(port)
    except:
        print "unparseable master location '%s'" % master
        print " expecting something more like localhost:8007 or localhost"
        raise

    asd = config['allow-shutdown']
    if asd:
        config['allow-shutdown'] = "'%s'" % asd

    if config['no-logrotate']:
        slaveTAC = "".join([slaveTACTemplate[0]] + slaveTACTemplate[2:])
    else:
        slaveTAC = "".join(slaveTACTemplate)
    contents = slaveTAC % config

    m.makeTAC(contents, secret=True)
    m.mkinfo()

    if not m.quiet:
        print "buildslave configured in %s" % m.basedir


class SlaveNotRunning(Exception):
    """
    raised when trying to stop slave process that is not running
    """


def stopSlave(basedir, quiet, signame="TERM"):
    """
    Stop slave process by sending it a signal.

    Using the specified basedir path, read slave process's pid file and
    try to terminate that process with specified signal.

    @param basedir: buildslave basedir path
    @param   quite: if False, don't print any messages to stdout
    @param signame: signal to send to the slave process

    @raise SlaveNotRunning: if slave pid file is not found
    """
    import signal

    os.chdir(basedir)
    try:
        f = open("twistd.pid", "rt")
    except:
        raise SlaveNotRunning()

    pid = int(f.read().strip())
    signum = getattr(signal, "SIG"+signame)
    timer = 0
    try:
        os.kill(pid, signum)
    except OSError, e:
        if e.errno != 3:
            raise

    time.sleep(0.1)
    while timer < 10:
        # poll once per second until twistd.pid goes away, up to 10 seconds
        try:
            os.kill(pid, 0)
        except OSError:
            if not quiet:
                print "buildslave process %d is dead" % pid
            return
        timer += 1
        time.sleep(1)
    if not quiet:
        print "never saw process go away"


def stop(config, signame="TERM"):
    quiet = config['quiet']
    basedir = config['basedir']

    if not base.isBuildslaveDir(basedir):
        sys.exit(1)

    try:
        stopSlave(basedir, quiet, signame)
    except SlaveNotRunning:
        if not quiet:
            print "buildslave not running"


def restart(config):
    quiet = config['quiet']

    if not base.isBuildslaveDir(config['basedir']):
        sys.exit(1)

    from buildslave.scripts.startup import start
    try:
        stopSlave(config['basedir'], quiet)
    except SlaveNotRunning:
        if not quiet:
            print "no old buildslave process found to stop"
    if not quiet:
        print "now restarting buildslave process.."
    start(config)


class MakerBase(usage.Options):
    optFlags = [
        ['help', 'h', "Display this message"],
        ["quiet", "q", "Do not emit the commands being run"],
        ]

    longdesc = """
    Operates upon the specified <basedir> (or the current directory, if not
    specified).
    """

    opt_h = usage.Options.opt_help

    def parseArgs(self, *args):
        if len(args) > 0:
            self['basedir'] = args[0]
        else:
            # Use the current directory if no basedir was specified.
            self['basedir'] = os.getcwd()
        if len(args) > 1:
            raise usage.UsageError("I wasn't expecting so many arguments")

    def postOptions(self):
        self['basedir'] = os.path.abspath(self['basedir'])

class StartOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ['nodaemon', None, "Don't daemonize (stay in foreground)"],
        ]
    def getSynopsis(self):
        return "Usage:    buildslave start [<basedir>]"

class StopOptions(MakerBase):
    def getSynopsis(self):
        return "Usage:    buildslave stop [<basedir>]"

class RestartOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ['nodaemon', None, "Don't daemonize (stay in foreground)"],
        ]
    def getSynopsis(self):
        return "Usage:    buildslave restart [<basedir>]"

class UpgradeSlaveOptions(MakerBase):
    optFlags = [
        ]
    optParameters = [
        ]

    def getSynopsis(self):
        return "Usage:    buildslave upgrade-slave [<basedir>]"

    longdesc = """
    This command takes an existing buildslave working directory and
    upgrades it to the current version.
    """

def upgradeSlave(config):
    basedir = os.path.expanduser(config['basedir'])

    if not base.isBuildslaveDir(basedir):
        sys.exit(1)

    buildbot_tac = open(os.path.join(basedir, "buildbot.tac")).read()
    new_buildbot_tac = buildbot_tac.replace(
        "from buildbot.slave.bot import BuildSlave",
        "from buildslave.bot import BuildSlave")
    if new_buildbot_tac != buildbot_tac:
        open(os.path.join(basedir, "buildbot.tac"), "w").write(new_buildbot_tac)
        print "buildbot.tac updated"
    else:
        print "No changes made"

    return 0


class CreateSlaveOptions(MakerBase):
    optFlags = [
        ["force", "f", "Re-use an existing directory"],
        ["relocatable", "r",
         "Create a relocatable buildbot.tac"],
        ["no-logrotate", "n",
         "Do not permit buildmaster rotate logs by itself"]
        ]
    optParameters = [
        ["keepalive", "k", 600,
         "Interval at which keepalives should be sent (in seconds)"],
        ["usepty", None, 0,
         "(1 or 0) child processes should be run in a pty (default 0)"],
        ["umask", None, "None",
         "controls permissions of generated files. Use --umask=022 to be world-readable"],
        ["maxdelay", None, 300,
         "Maximum time between connection attempts"],
        ["log-size", "s", "10000000",
         "size at which to rotate twisted log files"],
        ["log-count", "l", "10",
         "limit the number of kept old twisted log files (None for unlimited)"],
        ["allow-shutdown", "a", None,
         "Allows the buildslave to initiate a graceful shutdown. One of "
         "'signal' or 'file'"]
        ]

    longdesc = """
    This command creates a buildslave working directory and buildbot.tac
    file. The bot will use the <name> and <passwd> arguments to authenticate
    itself when connecting to the master. All commands are run in a
    build-specific subdirectory of <basedir>. <master> is a string of the
    form 'hostname[:port]', and specifies where the buildmaster can be reached.
    port defaults to 9989

    The appropriate values for <name>, <passwd>, and <master> should be
    provided to you by the buildmaster administrator. You must choose <basedir>
    yourself.
    """

    def getSynopsis(self):
        return "Usage:    buildslave create-slave [options] <basedir> <master> <name> <passwd>"

    def parseArgs(self, *args):
        if len(args) != 4:
            raise usage.UsageError("incorrect number of arguments")
        basedir, master, name, passwd = args
        if master[:5] == "http:":
            raise usage.UsageError("<master> is not a URL - do not use URL")
        self['basedir'] = basedir
        self['master'] = master
        self['name'] = name
        self['passwd'] = passwd

    def postOptions(self):
        MakerBase.postOptions(self)

        # check and convert numeric parameters
        for argument in ["usepty", "keepalive", "maxdelay", "log-size"]:
            try:
                self[argument] = int(self[argument])
            except ValueError:
                raise usage.UsageError("%s parameter needs to be an number" \
                                                                    % argument)

        if not re.match('^\d+$', self['log-count']) and \
                self['log-count'] != 'None':
            raise usage.UsageError("log-count parameter needs to be an number"
                                   " or None")

class Options(usage.Options):
    synopsis = "Usage:    buildslave <command> [command options]"

    subCommands = [
        # the following are all admin commands
        ['create-slave', None, CreateSlaveOptions,
         "Create and populate a directory for a new buildslave"],
        ['upgrade-slave', None, UpgradeSlaveOptions,
         "Upgrade an existing buildslave directory for the current version"],
        ['start', None, StartOptions, "Start a buildslave"],
        ['stop', None, StopOptions, "Stop a buildslave"],
        ['restart', None, RestartOptions,
         "Restart a buildslave"],
        ]

    def opt_version(self):
        import buildslave
        print "Buildslave version: %s" % buildslave.version
        usage.Options.opt_version(self)

    def opt_verbose(self):
        from twisted.python import log
        log.startLogging(sys.stderr)

    def postOptions(self):
        if not hasattr(self, 'subOptions'):
            raise usage.UsageError("must specify a command")


def run():
    config = Options()
    try:
        config.parseOptions()
    except usage.error, e:
        print "%s:  %s" % (sys.argv[0], e)
        print
        c = getattr(config, 'subOptions', config)
        print str(c)
        sys.exit(1)

    command = config.subCommand
    so = config.subOptions

    if command == "create-slave":
        createSlave(so)
    elif command == "upgrade-slave":
        upgradeSlave(so)
    elif command == "start":
        from buildslave.scripts.startup import start
        start(so)
    elif command == "stop":
        stop(so)
    elif command == "restart":
        restart(so)
    sys.exit(0)

