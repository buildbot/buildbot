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
#
# Also don't forget to mirror your changes on command-line options in manual
# pages and texinfo documentation.

import copy
import os, sys, stat, re, time
from twisted.python import usage, util, runtime
from twisted.internet import defer, reactor

from buildbot.interfaces import BuildbotNotRunningError

def in_reactor(f):
    """decorate a function by running it with maybeDeferred in a reactor"""
    def wrap(*args, **kwargs):
        from twisted.internet import reactor
        result = [ ]
        def async():
            d = defer.maybeDeferred(f, *args, **kwargs)
            def eb(f):
                f.printTraceback()
            d.addErrback(eb)
            def do_stop(r):
                result.append(r)
                reactor.stop()
            d.addBoth(do_stop)
        reactor.callWhenRunning(async)
        reactor.run()
        return result[0]
    return wrap

def isBuildmasterDir(dir):
    buildbot_tac = os.path.join(dir, "buildbot.tac")
    if not os.path.isfile(buildbot_tac):
        print "no buildbot.tac"
        return False

    contents = open(buildbot_tac, "r").read()
    return "Application('buildmaster')" in contents

# the create/start/stop commands should all be run as the same user,
# preferably a separate 'buildbot' account.

# Note that the terms 'options' and 'config' are used intechangeably here - in
# fact, they are intercanged several times.  Caveat legator.

class OptionsWithOptionsFile(usage.Options):
    # subclasses should set this to a list-of-lists in order to source the
    # .buildbot/options file.
    # buildbotOptions = [ [ 'optfile-name', 'option-name' ], .. ]
    buildbotOptions = None

    def __init__(self, *args):
        # for options in self.buildbotOptions, optParameters, and the options
        # file, change the default in optParameters *before* calling through
        # to the parent constructor

        # Options uses reflect.accumulateClassList, so this *must* be
        # a class attribute; however, we do not want to permanently change
        # the class.  So we patch it temporarily and restore it after.
        cls = self.__class__
        if hasattr(cls, 'optParameters'):
            old_optParameters = cls.optParameters
            cls.optParameters = op = copy.deepcopy(cls.optParameters)
            if self.buildbotOptions:
                optfile = loadOptionsFile()
                for optfile_name, option_name in self.buildbotOptions:
                    for i in range(len(op)):
                        if (op[i][0] == option_name and optfile_name in optfile):
                            op[i] = list(op[i])
                            op[i][2] = optfile[optfile_name]
        usage.Options.__init__(self, *args)
        if hasattr(cls, 'optParameters'):
            cls.optParameters = old_optParameters

def loadOptionsFile():
    """Find the .buildbot/FILENAME file. Crawl from the current directory up
    towards the root, and also look in ~/.buildbot . The first directory
    that's owned by the user and has the file we're looking for wins. Windows
    skips the owned-by-user test.
    
    @rtype:  dict
    @return: a dictionary of names defined in the options file. If no options
             file was found, return an empty dict.
    """

    here = os.path.abspath(os.getcwd())

    if runtime.platformType == 'win32':
        # never trust env-vars, use the proper API
        from win32com.shell import shellcon, shell
        appdata = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
        home = os.path.join(appdata, "buildbot")
    else:
        home = os.path.expanduser("~/.buildbot")

    searchpath = []
    toomany = 20
    while True:
        searchpath.append(os.path.join(here, ".buildbot"))
        next = os.path.dirname(here)
        if next == here:
            break # we've hit the root
        here = next
        toomany -= 1 # just in case
        if toomany == 0:
            raise ValueError("Hey, I seem to have wandered up into the "
                             "infinite glories of the heavens. Oops.")
    searchpath.append(home)

    localDict = {}

    for d in searchpath:
        if os.path.isdir(d):
            if runtime.platformType != 'win32':
                if os.stat(d)[stat.ST_UID] != os.getuid():
                    print "skipping %s because you don't own it" % d
                    continue # security, skip other people's directories
            optfile = os.path.join(d, "options")
            if os.path.exists(optfile):
                try:
                    f = open(optfile, "r")
                    options = f.read()
                    exec options in localDict
                except:
                    print "error while reading %s" % optfile
                    raise
                break

    for k in localDict.keys():
        if k.startswith("__"):
            del localDict[k]
    return localDict

class MakerBase(OptionsWithOptionsFile):
    optFlags = [
        ['help', 'h', "Display this message"],
        ["quiet", "q", "Do not emit the commands being run"],
        ]

    usage.Options.longdesc = """
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

makefile_sample = """# -*- makefile -*-

# This is a simple makefile which lives in a buildmaster
# directory (next to the buildbot.tac file). It allows you to start/stop the
# master by doing 'make start' or 'make stop'.

# The 'reconfig' target will tell a buildmaster to reload its config file.

start:
	twistd --no_save -y buildbot.tac

stop:
	if [ -e twistd.pid ]; \\
	then kill `cat twistd.pid`; \\
	else echo "Nothing to stop."; \\
	fi

reconfig:
	if [ -e twistd.pid ]; \\
	then kill -HUP `cat twistd.pid`; \\
	else echo "Nothing to reconfig."; \\
	fi

log:
	if [ -e twistd.log ]; \\
	then tail -f twistd.log; \\
	else echo "Nothing to tail."; \\
	fi
"""

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
        if not self.quiet: print "mkdir", self.basedir
        os.mkdir(self.basedir)

    def chdir(self):
        if not self.quiet: print "chdir", self.basedir
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

    def makefile(self):
        target = "Makefile.sample"
        if os.path.exists(target):
            oldcontents = open(target, "rt").read()
            if oldcontents == makefile_sample:
                if not self.quiet:
                    print "Makefile.sample already exists and is correct"
                return
            if not self.quiet:
                print "replacing Makefile.sample"
        else:
            if not self.quiet:
                print "creating Makefile.sample"
        f = open(target, "wt")
        f.write(makefile_sample)
        f.close()

    def sampleconfig(self, source):
        target = "master.cfg.sample"
        config_sample = open(source, "rt").read()
        if os.path.exists(target):
            oldcontents = open(target, "rt").read()
            if oldcontents == config_sample:
                if not self.quiet:
                    print "master.cfg.sample already exists and is up-to-date"
                return
            if not self.quiet:
                print "replacing master.cfg.sample"
        else:
            if not self.quiet:
                print "creating master.cfg.sample"
        f = open(target, "wt")
        f.write(config_sample)
        f.close()
        os.chmod(target, 0600)

    def public_html(self, files):
        webdir = os.path.join(self.basedir, "public_html")
        if os.path.exists(webdir):
            if not self.quiet:
                print "public_html/ already exists: not replacing"
            return
        else:
            os.mkdir(webdir)
        if not self.quiet:
            print "populating public_html/"
        for target, source in files.iteritems():
            target = os.path.join(webdir, target)
            f = open(target, "wt")
            f.write(open(source, "rt").read())
            f.close()

    def create_db(self):
        from buildbot.db import connector
        from buildbot.master import BuildMaster
        db = connector.DBConnector(BuildMaster(self.basedir),
                self.config['db'], basedir=self.basedir)
        if not self.config['quiet']: print "creating database"
        d = db.model.upgrade()
        return d

    def populate_if_missing(self, target, source, overwrite=False):
        new_contents = open(source, "rt").read()
        if os.path.exists(target):
            old_contents = open(target, "rt").read()
            if old_contents != new_contents:
                if overwrite:
                    if not self.quiet:
                        print "%s has old/modified contents" % target
                        print " overwriting it with new contents"
                    open(target, "wt").write(new_contents)
                else:
                    if not self.quiet:
                        print "%s has old/modified contents" % target
                        print " writing new contents to %s.new" % target
                    open(target + ".new", "wt").write(new_contents)
            # otherwise, it's up to date
        else:
            if not self.quiet:
                print "populating %s" % target
            open(target, "wt").write(new_contents)

    def move_if_present(self, source, dest):
        if os.path.exists(source):
            if os.path.exists(dest):
                print "Notice: %s now overrides %s" % (dest, source)
                print "        as the latter is not used by buildbot anymore."  
                print "        Decide which one you want to keep."
            else:
                try:
                    print "Notice: Moving %s to %s." % (source, dest)
                    print "        You can (and probably want to) remove it if  you haven't modified this file."
                    os.renames(source, dest)
                except Exception, e:
                    print "Error moving %s to %s: %s" % (source, dest, str(e))

    def upgrade_public_html(self, files):
        webdir = os.path.join(self.basedir, "public_html")
        if not os.path.exists(webdir):
            if not self.quiet:
                print "populating public_html/"
            os.mkdir(webdir)
        for target, source in files.iteritems():
            self.populate_if_missing(os.path.join(webdir, target),
                                 source)

    def check_master_cfg(self, expected_db_url=None):
        """Check the buildmaster configuration, returning a deferred that
        fires with an approprate exit status (so 0=success)."""
        from buildbot.master import BuildMaster
        from twisted.python import log

        master_cfg = os.path.join(self.basedir, "master.cfg")
        if not os.path.exists(master_cfg):
            if not self.quiet:
                print "No master.cfg found"
            return defer.succeed(1)

        # side-effects of loading the config file:

        #  for each Builder defined in c['builders'], if the status directory
        #  didn't already exist, it will be created, and the
        #  $BUILDERNAME/builder pickle might be created (with a single
        #  "builder created" event).

        # we put basedir in front of sys.path, because that's how the
        # buildmaster itself will run, and it is quite common to have the
        # buildmaster import helper classes from other .py files in its
        # basedir.

        if sys.path[0] != self.basedir:
            sys.path.insert(0, self.basedir)

        m = BuildMaster(self.basedir)

        # we need to route log.msg to stdout, so any problems can be seen
        # there. But if everything goes well, I'd rather not clutter stdout
        # with log messages. So instead we add a logObserver which gathers
        # messages and only displays them if something goes wrong.
        messages = []
        log.addObserver(messages.append)

        # this will errback if there's something wrong with the config file.
        # Note that this BuildMaster instance is never started, so it won't
        # actually do anything with the configuration.
        d = defer.maybeDeferred(lambda :
            m.loadConfig(open(master_cfg, "r"), checkOnly=True))
        def check_db_url(config):
            if (expected_db_url and 
                config.get('db_url', 'sqlite:///state.sqlite') != expected_db_url):
                raise ValueError("c['db_url'] in the config file ('%s') does"
                            " not match '%s'; please edit the configuration"
                            " file before upgrading." %
                                (config['db_url'], expected_db_url))
        d.addCallback(check_db_url)
        def cb(_):
            return 0
        def eb(f):
            if not self.quiet:
                print
                for m in messages:
                    print "".join(m['message'])
                f.printTraceback()
                print
                print "An error was detected in the master.cfg file."
                print "Please correct the problem and run 'buildbot upgrade-master' again."
                print
            return 1
        d.addCallbacks(cb, eb)
        return d

DB_HELP = """
    The --db string is evaluated to build the DB object, which specifies
    which database the buildmaster should use to hold scheduler state and
    status information. The default (which creates an SQLite database in
    BASEDIR/state.sqlite) is equivalent to:

      --db='sqlite:///state.sqlite'

    To use a remote MySQL database instead, use something like:

      --db='mysql://bbuser:bbpasswd@dbhost/bbdb'
"""

class UpgradeMasterOptions(MakerBase):
    optFlags = [
        ["replace", "r", "Replace any modified files without confirmation."],
        ]
    optParameters = [
        ["db", None, "sqlite:///state.sqlite",
         "which DB to use for scheduler/status state. See below for syntax."],
        ]

    def getSynopsis(self):
        return "Usage:    buildbot upgrade-master [options] [<basedir>]"

    longdesc = """
    This command takes an existing buildmaster working directory and
    adds/modifies the files there to work with the current version of
    buildbot. When this command is finished, the buildmaster directory should
    look much like a brand-new one created by the 'create-master' command.

    Use this after you've upgraded your buildbot installation and before you
    restart the buildmaster to use the new version.

    If you have modified the files in your working directory, this command
    will leave them untouched, but will put the new recommended contents in a
    .new file (for example, if index.html has been modified, this command
    will create index.html.new). You can then look at the new version and
    decide how to merge its contents into your modified file.
"""+DB_HELP+"""
    When upgrading from a pre-0.8.0 release (which did not use a database),
    this command will create the given database and migrate data from the old
    pickle files into it, then move the pickle files out of the way (e.g. to
    changes.pck.old). To revert to an older release, rename the pickle files
    back. When you are satisfied with the new version, you can delete the old
    pickle files.
    """

@in_reactor
@defer.deferredGenerator
def upgradeMaster(config):
    m = Maker(config)

    if not config['quiet']: print "upgrading basedir"
    basedir = os.path.expanduser(config['basedir'])
    # TODO: check Makefile
    # TODO: check TAC file
    # check web files: index.html, default.css, robots.txt
    m.upgrade_public_html({
            'bg_gradient.jpg' : util.sibpath(__file__, "../status/web/files/bg_gradient.jpg"),
            'default.css' : util.sibpath(__file__, "../status/web/files/default.css"),
            'robots.txt' : util.sibpath(__file__, "../status/web/files/robots.txt"),
            'favicon.ico' : util.sibpath(__file__, "../status/web/files/favicon.ico"),
        })
    m.populate_if_missing(os.path.join(basedir, "master.cfg.sample"),
                            util.sibpath(__file__, "sample.cfg"),
                            overwrite=True)
    # if index.html exists, use it to override the root page tempalte
    m.move_if_present(os.path.join(basedir, "public_html/index.html"),
                        os.path.join(basedir, "templates/root.html"))

    if not config['quiet']: print "checking master.cfg"
    wfd = defer.waitForDeferred(
            m.check_master_cfg(expected_db_url=config['db']))
    yield wfd
    rc = wfd.getResult()

    if rc == 0:
        from buildbot.db import connector
        from buildbot.master import BuildMaster

        if not config['quiet']: print "upgrading database"
        db = connector.DBConnector(BuildMaster(config['basedir']),
                            config['db'],
                            basedir=config['basedir'])

        wfd = defer.waitForDeferred(
                db.model.upgrade())
        yield wfd
        wfd.getResult()

        if not config['quiet']: print "upgrade complete"
        yield 0
    else:
        yield rc


class MasterOptions(MakerBase):
    optFlags = [
        ["force", "f",
         "Re-use an existing directory (will not overwrite master.cfg file)"],
        ["relocatable", "r",
         "Create a relocatable buildbot.tac"],
        ["no-logrotate", "n",
         "Do not permit buildmaster rotate logs by itself"]
        ]
    optParameters = [
        ["config", "c", "master.cfg", "name of the buildmaster config file"],
        ["log-size", "s", "10000000",
         "size at which to rotate twisted log files"],
        ["log-count", "l", "10",
         "limit the number of kept old twisted log files"],
        ["db", None, "sqlite:///state.sqlite",
         "which DB to use for scheduler/status state. See below for syntax."],
        ]
    def getSynopsis(self):
        return "Usage:    buildbot create-master [options] [<basedir>]"

    longdesc = """
    This command creates a buildmaster working directory and buildbot.tac file.
    The master will live in <dir> and create various files there.  If
    --relocatable is given, then the resulting buildbot.tac file will be
    written such that its containing directory is assumed to be the basedir.
    This is generally a good idea.

    At runtime, the master will read a configuration file (named
    'master.cfg' by default) in its basedir. This file should contain python
    code which eventually defines a dictionary named 'BuildmasterConfig'.
    The elements of this dictionary are used to configure the Buildmaster.
    See doc/config.xhtml for details about what can be controlled through
    this interface.
""" + DB_HELP + """
    The --db string is stored verbatim in the buildbot.tac file, and
    evaluated as 'buildbot start' time to pass a DBConnector instance into
    the newly-created BuildMaster object.
    """

    def postOptions(self):
        MakerBase.postOptions(self)
        if not re.match('^\d+$', self['log-size']):
            raise usage.UsageError("log-size parameter needs to be an int")
        if not re.match('^\d+$', self['log-count']) and \
                self['log-count'] != 'None':
            raise usage.UsageError("log-count parameter needs to be an int "+
                                   " or None")


masterTACTemplate = ["""
import os

from twisted.application import service
from buildbot.master import BuildMaster

basedir = r'%(basedir)s'
rotateLength = %(log-size)s
maxRotatedFiles = %(log-count)s

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path
    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a buildmaster
# directory; do not edit it.
application = service.Application('buildmaster')
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
configfile = r'%(config)s'

m = BuildMaster(basedir, configfile)
m.setServiceParent(application)
m.log_rotation.rotateLength = rotateLength
m.log_rotation.maxRotatedFiles = maxRotatedFiles

"""]

@in_reactor
def createMaster(config):
    m = Maker(config)
    m.mkdir()
    m.chdir()
    if config['relocatable']:
        config['basedir'] = '.'
    if config['no-logrotate']:
        masterTAC = "".join([masterTACTemplate[0]] + masterTACTemplate[2:])
    else:
        masterTAC = "".join(masterTACTemplate)
    contents = masterTAC % config
    m.makeTAC(contents)
    m.sampleconfig(util.sibpath(__file__, "sample.cfg"))
    m.public_html({
          'bg_gradient.jpg' : util.sibpath(__file__, "../status/web/files/bg_gradient.jpg"),
          'default.css' : util.sibpath(__file__, "../status/web/files/default.css"),
          'robots.txt' : util.sibpath(__file__, "../status/web/files/robots.txt"),
          'favicon.ico' : util.sibpath(__file__, "../status/web/files/favicon.ico"),
      })
    m.makefile()
    d = m.create_db()

    def print_status(r):
        if not m.quiet:
            print "buildmaster configured in %s" % m.basedir
    d.addCallback(print_status)
    return d

def stop(config, signame="TERM", wait=False):
    import signal
    basedir = config['basedir']
    quiet = config['quiet']

    if not isBuildmasterDir(config['basedir']):
        print "not a buildmaster directory"
        sys.exit(1)

    os.chdir(basedir)
    try:
        f = open("twistd.pid", "rt")
    except:
        raise BuildbotNotRunningError
    pid = int(f.read().strip())
    signum = getattr(signal, "SIG"+signame)
    timer = 0
    try:
        os.kill(pid, signum)
    except OSError, e:
        if e.errno != 3:
            raise

    if not wait:
        if not quiet:
            print "sent SIG%s to process" % signame
        return
    time.sleep(0.1)
    while timer < 10:
        # poll once per second until twistd.pid goes away, up to 10 seconds
        try:
            os.kill(pid, 0)
        except OSError:
            if not quiet:
                print "buildbot process %d is dead" % pid
            return
        timer += 1
        time.sleep(1)
    if not quiet:
        print "never saw process go away"

def restart(config):
    basedir = config['basedir']
    quiet = config['quiet']

    if not isBuildmasterDir(basedir):
        print "not a buildmaster directory"
        sys.exit(1)

    from buildbot.scripts.startup import start
    try:
        stop(config, wait=True)
    except BuildbotNotRunningError:
        pass
    if not quiet:
        print "now restarting buildbot process.."
    start(config)


class StartOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ]
    def getSynopsis(self):
        return "Usage:    buildbot start [<basedir>]"

class StopOptions(MakerBase):
    def getSynopsis(self):
        return "Usage:    buildbot stop [<basedir>]"

class ReconfigOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display log messages about reconfiguration"],
        ]
    def getSynopsis(self):
        return "Usage:    buildbot reconfig [<basedir>]"



class RestartOptions(MakerBase):
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ]
    def getSynopsis(self):
        return "Usage:    buildbot restart [<basedir>]"

class DebugClientOptions(OptionsWithOptionsFile):
    optFlags = [
        ['help', 'h', "Display this message"],
        ]
    optParameters = [
        ["master", "m", None,
         "Location of the buildmaster's slaveport (host:port)"],
        ["passwd", "p", None, "Debug password to use"],
        ]
    buildbotOptions = [
        [ 'debugMaster', 'passwd' ],
        [ 'master', 'master' ],
        ]
    def getSynopsis(self):
        return "Usage:    buildbot debugclient [options]"

    def parseArgs(self, *args):
        if len(args) > 0:
            self['master'] = args[0]
        if len(args) > 1:
            self['passwd'] = args[1]
        if len(args) > 2:
            raise usage.UsageError("I wasn't expecting so many arguments")

def debugclient(config):
    from buildbot.clients import debug

    master = config.get('master')
    if master is None:
        raise usage.UsageError("master must be specified: on the command "
                               "line or in ~/.buildbot/options")

    passwd = config.get('passwd')
    if passwd is None:
        raise usage.UsageError("passwd must be specified: on the command "
                               "line or in ~/.buildbot/options")

    d = debug.DebugWidget(master, passwd)
    d.run()

class StatusClientOptions(OptionsWithOptionsFile):
    optFlags = [
        ['help', 'h', "Display this message"],
        ]
    optParameters = [
        ["master", "m", None,
         "Location of the buildmaster's status port (host:port)"],
        ["username", "u", "statusClient", "Username performing the trial build"],
        ["passwd", None, "clientpw", "password for PB authentication"],
        ]
    buildbotOptions = [
        [ 'masterstatus', 'master' ],
    ]

    def parseArgs(self, *args):
        if len(args) > 0:
            self['master'] = args[0]
        if len(args) > 1:
            raise usage.UsageError("I wasn't expecting so many arguments")

class StatusLogOptions(StatusClientOptions):
    def getSynopsis(self):
        return "Usage:    buildbot statuslog [options]"

class StatusGuiOptions(StatusClientOptions):
    def getSynopsis(self):
        return "Usage:    buildbot statusgui [options]"

def statuslog(config):
    from buildbot.clients import base
    master = config.get('master')
    if master is None:
        raise usage.UsageError("master must be specified: on the command "
                               "line or in ~/.buildbot/options")
    passwd = config.get('passwd')
    username = config.get('username')
    c = base.TextClient(master, username=username, passwd=passwd)
    c.run()

def statusgui(config):
    from buildbot.clients import gtkPanes
    master = config.get('master')
    if master is None:
        raise usage.UsageError("master must be specified: on the command "
                               "line or in ~/.buildbot/options")
    passwd = config.get('passwd')
    username = config.get('username')
    c = gtkPanes.GtkClient(master, username=username, passwd=passwd)
    c.run()

class SendChangeOptions(OptionsWithOptionsFile):
    def __init__(self):
        OptionsWithOptionsFile.__init__(self)
        self['properties'] = {}

    optParameters = [
        ("master", "m", None,
         "Location of the buildmaster's PBListener (host:port)"),
        # deprecated in 0.8.3; remove in 0.8.5 (bug #1711)
        ("username", "u", None, "deprecated name for --who"),
        ("auth", "a", None, "Authentication token - username:password, or prompt for password"),
        ("who", "W", None, "Author of the commit"),
        ("repository", "R", '', "Repository specifier"),
        ("project", "P", '', "Project specifier"),
        ("branch", "b", None, "Branch specifier"),
        ("category", "C", None, "Category of repository"),
        ("revision", "r", None, "Revision specifier"),
        ("revision_file", None, None, "Filename containing revision spec"),
        ("property", "p", None,
         "A property for the change, in the format: name:value"),
        ("comments", "c", None, "log message"),
        ("logfile", "F", None,
         "Read the log messages from this file (- for stdin)"),
        ("when", "w", None, "timestamp to use as the change time"),
        ("revlink", "l", '', "Revision link (revlink)"),
        ("encoding", "e", 'utf8',
            "Encoding of other parameters (default utf8)"),
        ]

    buildbotOptions = [
        [ 'master', 'master' ],
        [ 'who', 'who' ],
        # deprecated in 0.8.3; remove in 0.8.5 (bug #1711)
        [ 'username', 'username' ],
        [ 'branch', 'branch' ],
        [ 'category', 'category' ],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot sendchange [options] filenames.."
    def parseArgs(self, *args):
        self['files'] = args
    def opt_property(self, property):
        name,value = property.split(':')
        self['properties'][name] = value


def sendchange(config, runReactor=False):
    """Send a single change to the buildmaster's PBChangeSource. The
    connection will be drpoped as soon as the Change has been sent."""
    from buildbot.clients import sendchange

    encoding = config.get('encoding', 'utf8')
    who = config.get('who')
    if not who and config.get('username'):
        print "NOTE: --username/-u is deprecated: use --who/-W'"
        who = config.get('username')
    auth = config.get('auth')
    master = config.get('master')
    branch = config.get('branch')
    category = config.get('category')
    revision = config.get('revision')
    properties = config.get('properties', {})
    repository = config.get('repository', '')
    project = config.get('project', '')
    revlink = config.get('revlink', '')
    if config.get('when'):
        when = float(config.get('when'))
    else:
        when = None
    if config.get("revision_file"):
        revision = open(config["revision_file"],"r").read()

    comments = config.get('comments')
    if not comments and config.get('logfile'):
        if config['logfile'] == "-":
            f = sys.stdin
        else:
            f = open(config['logfile'], "rt")
        comments = f.read()
    if comments is None:
        comments = ""

    files = config.get('files', ())

    # fix up the auth with a password if none was given
    if not auth:
        auth = 'change:changepw'
    if ':' not in auth:
        import getpass
        pw = getpass.getpass("Enter password for '%s': " % auth)
        auth = "%s:%s" % (auth, pw)
    auth = auth.split(':', 1)

    assert who, "you must provide a committer (--who)"
    assert master, "you must provide the master location"

    s = sendchange.Sender(master, auth, encoding=encoding)
    d = s.send(branch, revision, comments, files, who=who, category=category, when=when,
               properties=properties, repository=repository, project=project,
               revlink=revlink)

    if runReactor:
        status = [True]
        def printSuccess(_):
            print "change sent successfully"
        def failed(f):
            status[0] = False
            print "change NOT sent - something went wrong: " + str(f)
        d.addCallbacks(printSuccess, failed)
        d.addBoth(lambda _ : reactor.stop())
        reactor.run()
        return status[0]
    return d


class ForceOptions(OptionsWithOptionsFile):
    optParameters = [
        ["builder", None, None, "which Builder to start"],
        ["branch", None, None, "which branch to build"],
        ["revision", None, None, "which revision to build"],
        ["reason", None, None, "the reason for starting the build"],
        ]

    def parseArgs(self, *args):
        args = list(args)
        if len(args) > 0:
            if self['builder'] is not None:
                raise usage.UsageError("--builder provided in two ways")
            self['builder'] = args.pop(0)
        if len(args) > 0:
            if self['reason'] is not None:
                raise usage.UsageError("--reason provided in two ways")
            self['reason'] = " ".join(args)


class TryOptions(OptionsWithOptionsFile):
    optParameters = [
        ["connect", "c", None,
         "How to reach the buildmaster, either 'ssh' or 'pb'"],
        # for ssh, use --host, --username, and --jobdir
        ["host", None, None,
         "Hostname (used by ssh) for the buildmaster"],
        ["jobdir", None, None,
         "Directory (on the buildmaster host) where try jobs are deposited"],
        ["username", "u", None,
         "Username performing the try build"],
        # for PB, use --master, --username, and --passwd
        ["master", "m", None,
         "Location of the buildmaster's PBListener (host:port)"],
        ["passwd", None, None,
         "Password for PB authentication"],
        ["who", "w", None,
         "Who is responsible for the try build"],

        ["diff", None, None,
         "Filename of a patch to use instead of scanning a local tree. "
         "Use '-' for stdin."],
        ["patchlevel", "p", 0,
         "Number of slashes to remove from patch pathnames, "
         "like the -p option to 'patch'"],

        ["baserev", None, None,
         "Base revision to use instead of scanning a local tree."],

        ["vc", None, None,
         "The VC system in use, one of: bzr, cvs, darcs, git, hg, "
         "mtn, p4, svn"],
        ["branch", None, None,
         "The branch in use, for VC systems that can't figure it out "
         "themselves"],
        ["repository", None, None,
         "Repository to use, instead of path to working directory."],

        ["builder", "b", None,
         "Run the trial build on this Builder. Can be used multiple times."],
        ["properties", None, None,
         "A set of properties made available in the build environment, "
         "format:prop1=value1,prop2=value2..."],

        ["topfile", None, None,
         "Name of a file at the top of the tree, used to find the top. "
         "Only needed for SVN and CVS."],
        ["topdir", None, None,
         "Path to the top of the working copy. Only needed for SVN and CVS."],
    ]

    optFlags = [
        ["wait", None,
         "wait until the builds have finished"],
        ["dryrun", 'n',
         "Gather info, but don't actually submit."],
        ["get-builder-names", None,
         "Get the names of available builders. Doesn't submit anything. "
         "Only supported for 'pb' connections."],
        ["quiet", "q",
         "Don't print status of current builds while waiting."],
    ]

    # Mapping of .buildbot/options names to command-line options
    buildbotOptions = [
        [ 'try_connect', 'connect' ],
        #[ 'try_builders', 'builders' ], <-- handled in postOptions
        [ 'try_vc', 'vc' ],
        [ 'try_branch', 'branch' ],
        [ 'try_repository', 'repository' ],
        [ 'try_topdir', 'topdir' ],
        [ 'try_topfile', 'topfile' ],
        [ 'try_host', 'host' ],
        [ 'try_username', 'username' ],
        [ 'try_jobdir', 'jobdir' ],
        [ 'try_password', 'passwd' ],
        [ 'try_master', 'master' ],
        [ 'try_who', 'who' ],
        #[ 'try_wait', 'wait' ], <-- handled in postOptions
        [ 'try_masterstatus', 'masterstatus' ],
        # Deprecated command mappings from the quirky old days:
        [ 'try_topdir', 'try-topdir' ],
        [ 'try_topfile', 'try-topfile' ],
        [ 'try_host', 'tryhost' ],
        [ 'try_dir', 'trydir' ],        # replaced by try_jobdir/jobdir
        [ 'masterstatus', 'master' ],   # replaced by try_masterstatus/masterstatus
    ]

    def __init__(self):
        OptionsWithOptionsFile.__init__(self)
        self['builders'] = []
        self['properties'] = {}

    def opt_builder(self, option):
        self['builders'].append(option)

    def opt_properties(self, option):
        # We need to split the value of this option into a dictionary of properties
        properties = {}
        propertylist = option.split(",")
        for i in range(0,len(propertylist)):
            print propertylist[i]
            splitproperty = propertylist[i].split("=")
            properties[splitproperty[0]] = splitproperty[1]
        self['properties'] = properties

    def opt_patchlevel(self, option):
        self['patchlevel'] = int(option)

    def getSynopsis(self):
        return "Usage:    buildbot try [options]"

    def postOptions(self):
        opts = loadOptionsFile()
        if not self['builders']:
            self['builders'] = opts.get('try_builders', [])
        if opts.get('try_wait', False):
            self['wait'] = True
        if opts.get('try_quiet', False):
            self['quiet'] = True

def doTry(config):
    from buildbot.clients import tryclient
    t = tryclient.Try(config)
    t.run()

class TryServerOptions(OptionsWithOptionsFile):
    optParameters = [
        ["jobdir", None, None, "the jobdir (maildir) for submitting jobs"],
        ]
    def getSynopsis(self):
        return "Usage:    buildbot tryserver [options]"


def doTryServer(config):
    try:
        from hashlib import md5
        assert md5
    except ImportError:
        # For Python 2.4 compatibility
        import md5
    jobdir = os.path.expanduser(config["jobdir"])
    job = sys.stdin.read()
    # now do a 'safecat'-style write to jobdir/tmp, then move atomically to
    # jobdir/new . Rather than come up with a unique name randomly, I'm just
    # going to MD5 the contents and prepend a timestamp.
    timestring = "%d" % time.time()
    try:
        m = md5()
    except TypeError:
        # For Python 2.4 compatibility
        m = md5.new()
    m.update(job)
    jobhash = m.hexdigest()
    fn = "%s-%s" % (timestring, jobhash)
    tmpfile = os.path.join(jobdir, "tmp", fn)
    newfile = os.path.join(jobdir, "new", fn)
    f = open(tmpfile, "w")
    f.write(job)
    f.close()
    os.rename(tmpfile, newfile)


class CheckConfigOptions(OptionsWithOptionsFile):
    optFlags = [
        ['quiet', 'q', "Don't display error messages or tracebacks"],
    ]

    def getSynopsis(self):
        return "Usage:		buildbot checkconfig [configFile]\n" + \
         "		If not specified, 'master.cfg' will be used as 'configFile'"

    def parseArgs(self, *args):
        if len(args) >= 1:
            self['configFile'] = args[0]
        else:
            self['configFile'] = 'master.cfg'


@in_reactor
def doCheckConfig(config):
    from buildbot.scripts.checkconfig import ConfigLoader
    quiet = config.get('quiet')
    configFileName = config.get('configFile')

    if os.path.isdir(configFileName):
        cl = ConfigLoader(basedir=configFileName)
    else:
        cl = ConfigLoader(configFileName=configFileName)

    d = cl.load()

    def cb(r):
        if not quiet:
            print "Config file is good!"
        return True
    def eb(f):
        if not quiet:
            f.printTraceback()
        return False
    d.addCallbacks(cb, eb)

    return d

class Options(usage.Options):
    synopsis = "Usage:    buildbot <command> [command options]"

    subCommands = [
        # the following are all admin commands
        ['create-master', None, MasterOptions,
         "Create and populate a directory for a new buildmaster"],
        ['upgrade-master', None, UpgradeMasterOptions,
         "Upgrade an existing buildmaster directory for the current version"],
        ['start', None, StartOptions, "Start a buildmaster"],
        ['stop', None, StopOptions, "Stop a buildmaster"],
        ['restart', None, RestartOptions,
         "Restart a buildmaster"],

        ['reconfig', None, ReconfigOptions,
         "SIGHUP a buildmaster to make it re-read the config file"],
        ['sighup', None, ReconfigOptions,
         "SIGHUP a buildmaster to make it re-read the config file"],

        ['sendchange', None, SendChangeOptions,
         "Send a change to the buildmaster"],

        ['debugclient', None, DebugClientOptions,
         "Launch a small debug panel GUI"],

        ['statuslog', None, StatusLogOptions,
         "Emit current builder status to stdout"],
        ['statusgui', None, StatusGuiOptions,
         "Display a small window showing current builder status"],

        #['force', None, ForceOptions, "Run a build"],
        ['try', None, TryOptions, "Run a build with your local changes"],

        ['tryserver', None, TryServerOptions,
         "buildmaster-side 'try' support function, not for users"],

        ['checkconfig', None, CheckConfigOptions,
         "test the validity of a master.cfg config file"],

        # TODO: 'watch'
        ]

    def opt_version(self):
        import buildbot
        print "Buildbot version: %s" % buildbot.version
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

    if command == "create-master":
        createMaster(so)
    elif command == "upgrade-master":
        upgradeMaster(so)
    elif command == "start":
        from buildbot.scripts.startup import start

        if not isBuildmasterDir(so['basedir']):
            print "not a buildmaster directory"
            sys.exit(1)

        start(so)
    elif command == "stop":
        try:
            stop(so, wait=True)
        except BuildbotNotRunningError:
            if not so['quiet']:
                print "buildmaster not running"
            sys.exit(0)

    elif command == "restart":
        restart(so)
    elif command == "reconfig" or command == "sighup":
        from buildbot.scripts.reconfig import Reconfigurator
        Reconfigurator().run(so)
    elif command == "sendchange":
        if not sendchange(so, True):
            sys.exit(1)
    elif command == "debugclient":
        debugclient(so)
    elif command == "statuslog":
        statuslog(so)
    elif command == "statusgui":
        statusgui(so)
    elif command == "try":
        doTry(so)
    elif command == "tryserver":
        doTryServer(so)
    elif command == "checkconfig":
        if not doCheckConfig(so):
            sys.exit(1)
    sys.exit(0)

