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
#
# N.B.: don't import anything that might pull in a reactor yet. Some of our
# subcommands want to load modules that need the gtk reactor.
#
# Also don't forget to mirror your changes on command-line options in manual
# pages and texinfo documentation.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.builtins import range

import sys
import textwrap

import sqlalchemy as sa

from twisted.python import reflect
from twisted.python import usage

from buildbot.scripts import base

# Note that the terms 'options' and 'config' are used interchangeably here - in
# fact, they are interchanged several times.  Caveat legator.


def validateMasterOption(master):
    """
    Validate master (-m, --master) command line option.

    Checks that option is a string of the 'hostname:port' form, otherwise
    raises an UsageError exception.

    @type  master: string
    @param master: master option

    @raise usage.UsageError: on invalid master option
    """
    try:
        hostname, port = master.split(":")
        port = int(port)
    except (TypeError, ValueError):
        raise usage.UsageError("master must have the form 'hostname:port'")


class UpgradeMasterOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.upgrade_master.upgradeMaster"
    optFlags = [
        ["quiet", "q", "Do not emit the commands being run"],
        ["develop", "d", "link to buildbot dir rather than copy, with no "
                         "JS optimization (UNIX only)"],
        ["replace", "r", "Replace any modified files without confirmation."],
    ]
    optParameters = [
    ]

    def getSynopsis(self):
        return "Usage:    buildbot upgrade-master [options] [<basedir>]"

    longdesc = textwrap.dedent("""
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

    When upgrading the database, this command uses the database specified in
    the master configuration file.  If you wish to use a database other than
    the default (sqlite), be sure to set that parameter before upgrading.
    """)


class CreateMasterOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.create_master.createMaster"
    optFlags = [
        ["quiet", "q", "Do not emit the commands being run"],
        ["force", "f",
         "Re-use an existing directory (will not overwrite master.cfg file)"],
        ["relocatable", "r",
         "Create a relocatable buildbot.tac"],
        ["develop", "d", "link to buildbot dir rather than copy, with no "
                         "JS optimization (UNIX only)"],
        ["no-logrotate", "n",
         "Do not permit buildmaster rotate logs by itself"]
    ]
    optParameters = [
        ["config", "c", "master.cfg", "name of the buildmaster config file"],
        ["log-size", "s", 10000000,
         "size at which to rotate twisted log files", int],
        ["log-count", "l", 10,
         "limit the number of kept old twisted log files"],
        ["db", None, "sqlite:///state.sqlite",
         "which DB to use for scheduler/status state. See below for syntax."],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot create-master [options] [<basedir>]"

    longdesc = textwrap.dedent("""
    This command creates a buildmaster working directory and buildbot.tac file.
    The master will live in <basedir> (defaults to the current directory)
    and create various files there.
    If --relocatable is given, then the resulting buildbot.tac file will be
    written such that its containing directory is assumed to be the basedir.
    This is generally a good idea.

    At runtime, the master will read a configuration file (named
    'master.cfg' by default) in its basedir. This file should contain python
    code which eventually defines a dictionary named 'BuildmasterConfig'.
    The elements of this dictionary are used to configure the Buildmaster.
    See doc/config.xhtml for details about what can be controlled through
    this interface.

    The --db string is evaluated to build the DB object, which specifies
    which database the buildmaster should use to hold scheduler state and
    status information. The default (which creates an SQLite database in
    BASEDIR/state.sqlite) is equivalent to:

      --db='sqlite:///state.sqlite'

    To use a remote MySQL database instead, use something like:

      --db='mysql://bbuser:bbpasswd@dbhost/bbdb'
    The --db string is stored verbatim in the buildbot.tac file, and
    evaluated at 'buildbot start' time to pass a DBConnector instance into
    the newly-created BuildMaster object.
    """)

    def postOptions(self):
        base.BasedirMixin.postOptions(self)

        # validate 'log-count' parameter
        if self['log-count'] == 'None':
            self['log-count'] = None
        else:
            try:
                self['log-count'] = int(self['log-count'])
            except ValueError:
                raise usage.UsageError(
                    "log-count parameter needs to be an int or None")

        # validate 'db' parameter
        try:
            # check if sqlalchemy will be able to parse specified URL
            sa.engine.url.make_url(self['db'])
        except sa.exc.ArgumentError:
            raise usage.UsageError("could not parse database URL '%s'"
                                   % self['db'])


class StopOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.stop.stop"
    optFlags = [
        ["quiet", "q", "Do not emit the commands being run"],
        ["clean", "c", "Clean shutdown master"],
        ["no-wait", None, "Don't wait for complete master shutdown"],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot stop [<basedir>]"


class RestartOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.restart.restart"
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ['nodaemon', None, "Don't daemonize (stay in foreground)"],
        ["clean", "c", "Clean shutdown master"],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot restart [<basedir>]"


class StartOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.start.start"
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ['nodaemon', None, "Don't daemonize (stay in foreground)"],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot start [<basedir>]"


class ReconfigOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.reconfig.reconfig"
    optFlags = [
        ['quiet', 'q', "Don't display log messages about reconfiguration"],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot reconfig [<basedir>]"


class SendChangeOptions(base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.sendchange.sendchange"

    def __init__(self):
        base.SubcommandOptions.__init__(self)
        self['properties'] = {}

    optParameters = [
        ("master", "m", None,
         "Location of the buildmaster's PBChangeSource (host:port)"),
        # deprecated in 0.8.3; remove in 0.8.5 (bug #1711)
        ("auth", "a", 'change:changepw',
         "Authentication token - username:password, or prompt for password"),
        ("who", "W", None, "Author of the commit"),
        ("repository", "R", '', "Repository specifier"),
        ("vc", "s", None, "The VC system in use, one of: cvs, svn, darcs, hg, "
         "bzr, git, mtn, p4"),
        ("project", "P", '', "Project specifier"),
        ("branch", "b", None, "Branch specifier"),
        ("category", "C", None, "Category of repository"),
        ("codebase", None, None,
            "Codebase this change is in (requires 0.8.7 master or later)"),
        ("revision", "r", None, "Revision specifier"),
        ("revision_file", None, None, "Filename containing revision spec"),
        ("property", "p", None,
         "A property for the change, in the format: name:value"),
        ("comments", "c", None, "log message"),
        ("logfile", "F", None,
         "Read the log messages from this file (- for stdin)"),
        ("when", "w", None, "timestamp to use as the change time"),
        ("revlink", "l", '', "Revision link (revlink)"),
        ("encoding", "e", 'utf8', "Encoding of other parameters"),
    ]

    buildbotOptions = [
        ['master', 'master'],
        ['who', 'who'],
        ['branch', 'branch'],
        ['category', 'category'],
        ['vc', 'vc'],
    ]

    requiredOptions = ['who', 'master']

    def getSynopsis(self):
        return "Usage:    buildbot sendchange [options] filenames.."

    def parseArgs(self, *args):
        self['files'] = args

    def opt_property(self, property):
        name, value = property.split(':', 1)
        self['properties'][name] = value

    def postOptions(self):
        base.SubcommandOptions.postOptions(self)

        if self.get("revision_file"):
            with open(self["revision_file"], "r") as f:
                self['revision'] = f.read()

        if self.get('when'):
            try:
                self['when'] = float(self['when'])
            except (TypeError, ValueError):
                raise usage.UsageError('invalid "when" value %s'
                                       % (self['when'],))
        else:
            self['when'] = None

        if not self.get('comments') and self.get('logfile'):
            if self['logfile'] == "-":
                self['comments'] = sys.stdin.read()
            else:
                with open(self['logfile'], "rt") as f:
                    self['comments'] = f.read()
        if self.get('comments') is None:
            self['comments'] = ""

        # fix up the auth with a password if none was given
        auth = self.get('auth')
        if ':' not in auth:
            import getpass
            pw = getpass.getpass("Enter password for '%s': " % auth)
            auth = "%s:%s" % (auth, pw)
        self['auth'] = tuple(auth.split(':', 1))

        vcs = ['cvs', 'svn', 'darcs', 'hg', 'bzr', 'git', 'mtn', 'p4']
        if self.get('vc') and self.get('vc') not in vcs:
            raise usage.UsageError("vc must be one of %s" % (', '.join(vcs)))

        validateMasterOption(self.get('master'))


class TryOptions(base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.trycmd.trycmd"
    optParameters = [
        ["connect", "c", None,
         "How to reach the buildmaster, either 'ssh' or 'pb'"],
        # for ssh, use --host, --username, --jobdir and optionally
        # --ssh
        ["host", None, None,
         "Hostname (used by ssh) for the buildmaster"],
        ["port", None, None,
         "Port (used by ssh) for the buildmaster"],
        ["jobdir", None, None,
         "Directory (on the buildmaster host) where try jobs are deposited"],
        ["ssh", None, None,
         "Command to use instead of the default \"ssh\""],
        ["username", "u", None,
         "Username performing the try build"],
        # for PB, use --master, --username, and --passwd
        ["master", "m", None,
         "Location of the buildmaster's Try server (host:port)"],
        ["passwd", None, None,
         "Password for PB authentication"],
        ["who", "w", None,
         "Who is responsible for the try build"],
        ["comment", "C", None,
         "A comment which can be used in notifications for this build"],

        # for ssh to accommodate running in a virtualenv on the buildmaster
        ["buildbotbin", None, "buildbot",
         "buildbot binary to use on the buildmaster host"],

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
         "format is --properties=prop1=value1,prop2=value2,.. "
         "option can be specified multiple times."],
        ["property", None, None,
         "A property made available in the build environment, "
         "format:prop=value. Can be used multiple times."],

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
        ['try_connect', 'connect'],
        # [ 'try_builders', 'builders' ], <-- handled in postOptions
        ['try_vc', 'vc'],
        ['try_branch', 'branch'],
        ['try_repository', 'repository'],
        ['try_topdir', 'topdir'],
        ['try_topfile', 'topfile'],
        ['try_host', 'host'],
        ['try_username', 'username'],
        ['try_jobdir', 'jobdir'],
        ['try_ssh', 'ssh'],
        ['try_buildbotbin', 'buildbotbin'],
        ['try_passwd', 'passwd'],
        ['try_master', 'master'],
        ['try_who', 'who'],
        ['try_comment', 'comment'],
        # [ 'try_wait', 'wait' ], <-- handled in postOptions
        # [ 'try_quiet', 'quiet' ], <-- handled in postOptions

        # Deprecated command mappings from the quirky old days:
        ['try_masterstatus', 'master'],
        ['try_dir', 'jobdir'],
        ['try_password', 'passwd'],
    ]

    def __init__(self):
        base.SubcommandOptions.__init__(self)
        self['builders'] = []
        self['properties'] = {}

    def opt_builder(self, option):
        self['builders'].append(option)

    def opt_properties(self, option):
        # We need to split the value of this option
        # into a dictionary of properties
        propertylist = option.split(",")
        for i in range(0, len(propertylist)):
            splitproperty = propertylist[i].split("=", 1)
            self['properties'][splitproperty[0]] = splitproperty[1]

    def opt_property(self, option):
        name, _, value = option.partition("=")
        self['properties'][name] = value

    def opt_patchlevel(self, option):
        self['patchlevel'] = int(option)

    def getSynopsis(self):
        return "Usage:    buildbot try [options]"

    def postOptions(self):
        base.SubcommandOptions.postOptions(self)
        opts = self.optionsFile
        if not self['builders']:
            self['builders'] = opts.get('try_builders', [])
        if opts.get('try_wait', False):
            self['wait'] = True
        if opts.get('try_quiet', False):
            self['quiet'] = True
        # get the global 'masterstatus' option if it's set and no master
        # was specified otherwise
        if not self['master']:
            self['master'] = opts.get('masterstatus', None)

        if self['connect'] == 'pb':
            if not self['master']:
                raise usage.UsageError("master location must be specified"
                                       "for 'pb' connections")
            validateMasterOption(self['master'])


class TryServerOptions(base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.tryserver.tryserver"
    optParameters = [
        ["jobdir", None, None, "the jobdir (maildir) for submitting jobs"],
    ]
    requiredOptions = ['jobdir']

    def getSynopsis(self):
        return "Usage:    buildbot tryserver [options]"

    def postOptions(self):
        if not self['jobdir']:
            raise usage.UsageError('jobdir is required')


class CheckConfigOptions(base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.checkconfig.checkconfig"
    optFlags = [
        ['quiet', 'q', "Don't display error messages or tracebacks"],
    ]

    # on tab completion, suggest files as first argument
    if hasattr(usage, 'Completions'):
        # only set completion suggestion if running with
        # twisted version (>=11.1.0) that supports it
        compData = usage.Completions(extraActions=[usage.CompleteFiles()])

    def getSynopsis(self):
        return "Usage:\t\tbuildbot checkconfig [configFile]\n" + \
            "\t\tIf not specified, the config file specified in " + \
            "'buildbot.tac' from the current directory will be used"

    def parseArgs(self, *args):
        if len(args) >= 1:
            self['configFile'] = args[0]


class UserOptions(base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.user.user"
    optParameters = [
        ["master", "m", None,
         "Location of the buildmaster's user service (host:port)"],
        ["username", "u", None,
         "Username for PB authentication"],
        ["passwd", "p", None,
         "Password for PB authentication"],
        ["op", None, None,
         "User management operation: add, remove, update, get"],
        ["bb_username", None, None,
         "Username to set for a given user. Only availabe on 'update', "
         "and bb_password must be given as well."],
        ["bb_password", None, None,
         "Password to set for a given user. Only availabe on 'update', "
         "and bb_username must be given as well."],
        ["ids", None, None,
         "User's identifiers, used to find users in 'remove' and 'get' "
         "Can be specified multiple times (--ids=id1,id2,id3)"],
        ["info", None, None,
         "User information in the form: --info=type=value,type=value,.. "
         "Used in 'add' and 'update', can be specified multiple times.  "
         "Note that 'update' requires --info=id:type=value..."]
    ]
    buildbotOptions = [
        ['master', 'master'],
        ['user_master', 'master'],
        ['user_username', 'username'],
        ['user_passwd', 'passwd'],
    ]
    requiredOptions = ['master']

    longdesc = textwrap.dedent("""
    Currently implemented types for --info= are:\n
    git, svn, hg, cvs, darcs, bzr, email
    """)

    def __init__(self):
        base.SubcommandOptions.__init__(self)
        self['ids'] = []
        self['info'] = []

    def opt_ids(self, option):
        id_list = option.split(",")
        self['ids'].extend(id_list)

    def opt_info(self, option):
        # splits info into type/value dictionary, appends to info
        info_list = option.split(",")
        info_elem = {}

        if len(info_list) == 1 and '=' not in info_list[0]:
            info_elem["identifier"] = info_list[0]
            self['info'].append(info_elem)
        else:
            for i in range(0, len(info_list)):
                split_info = info_list[i].split("=", 1)

                # pull identifier from update --info
                if ":" in split_info[0]:
                    split_id = split_info[0].split(":")
                    info_elem["identifier"] = split_id[0]
                    split_info[0] = split_id[1]

                info_elem[split_info[0]] = split_info[1]
            self['info'].append(info_elem)

    def getSynopsis(self):
        return "Usage:    buildbot user [options]"

    def _checkValidTypes(self, info):
        from buildbot.process.users import users
        valid = set(['identifier', 'email'] + users.srcs)

        for user in info:
            for attr_type in user:
                if attr_type not in valid:
                    raise usage.UsageError(
                        "Type not a valid attr_type, must be in: %s"
                        % ', '.join(valid))

    def postOptions(self):
        base.SubcommandOptions.postOptions(self)

        validateMasterOption(self.get('master'))

        op = self.get('op')
        if not op:
            raise usage.UsageError("you must specify an operation: add, "
                                   "remove, update, get")
        if op not in ['add', 'remove', 'update', 'get']:
            raise usage.UsageError("bad op %r, use 'add', 'remove', 'update', "
                                   "or 'get'" % op)

        if not self.get('username') or not self.get('passwd'):
            raise usage.UsageError("A username and password must be given")

        bb_username = self.get('bb_username')
        bb_password = self.get('bb_password')
        if bb_username or bb_password:
            if op != 'update':
                raise usage.UsageError("bb_username and bb_password only work "
                                       "with update")
            if not bb_username or not bb_password:
                raise usage.UsageError("Must specify both bb_username and "
                                       "bb_password or neither.")

        info = self.get('info')
        ids = self.get('ids')

        # check for erroneous args
        if not info and not ids:
            raise usage.UsageError("must specify either --ids or --info")

        if op == 'add' or op == 'update':
            if ids:
                raise usage.UsageError("cannot use --ids with 'add' or "
                                       "'update'")
            self._checkValidTypes(info)
            if op == 'update':
                for user in info:
                    if 'identifier' not in user:
                        raise usage.UsageError("no ids found in update info; "
                                               "use: --info=id:type=value,type=value,..")
            if op == 'add':
                for user in info:
                    if 'identifier' in user:
                        raise usage.UsageError("identifier found in add info, "
                                               "use: --info=type=value,type=value,..")
        if op == 'remove' or op == 'get':
            if info:
                raise usage.UsageError("cannot use --info with 'remove' "
                                       "or 'get'")


class DataSpecOption(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.dataspec.dataspec"
    optParameters = [
        ['out', 'o', "dataspec.json", "output to specified path"],
        ['global', 'g', None,
            "output a js script, that sets a global, for inclusion in testsuite"],
    ]

    def getSynopsis(self):
        return "Usage:   buildbot dataspec [options]"


class ProcessWWWIndexOption(base.BasedirMixin, base.SubcommandOptions):

    """This command is used with the front end's proxy task. It enables to run the front end
    without the backend server running in the background"""

    subcommandFunction = "buildbot.scripts.processwwwindex.processwwwindex"
    optParameters = [
        ['index-file', 'i', None,
            "Path to the index.html file to be processed"],
    ]


class CleanupDBOptions(base.BasedirMixin, base.SubcommandOptions):
    subcommandFunction = "buildbot.scripts.cleanupdb.cleanupDatabase"
    optFlags = [
        ["quiet", "q", "Do not emit the commands being run"],
        ["force", "f",
            "Force log recompression (useful when changing compression algorithm)"],
        # when this command has several maintainance jobs, we should make
        # them optional here. For now there is only one.
    ]
    optParameters = [
    ]

    def getSynopsis(self):
        return "Usage:    buildbot cleanupdb [options] [<basedir>]"

    longdesc = textwrap.dedent("""
    This command takes an existing buildmaster working directory and
    do some optimization on the database.

    This command is frontend for various database maintainance jobs:

    - optimiselogs: This optimization groups logs into bigger chunks
      to apply higher level of compression.

    This command uses the database specified in
    the master configuration file.  If you wish to use a database other than
    the default (sqlite), be sure to set that parameter before upgrading.
    """)


class Options(usage.Options):
    synopsis = "Usage:    buildbot <command> [command options]"

    subCommands = [
        ['create-master', None, CreateMasterOptions,
         "Create and populate a directory for a new buildmaster"],
        ['upgrade-master', None, UpgradeMasterOptions,
         "Upgrade an existing buildmaster directory for the current version"],
        ['start', None, StartOptions,
         "Start a buildmaster"],
        ['stop', None, StopOptions,
         "Stop a buildmaster"],
        ['restart', None, RestartOptions,
         "Restart a buildmaster"],
        ['reconfig', None, ReconfigOptions,
         "SIGHUP a buildmaster to make it re-read the config file"],
        ['sighup', None, ReconfigOptions,
         "SIGHUP a buildmaster to make it re-read the config file"],
        ['sendchange', None, SendChangeOptions,
         "Send a change to the buildmaster"],
        ['try', None, TryOptions,
         "Run a build with your local changes"],
        ['tryserver', None, TryServerOptions,
         "buildmaster-side 'try' support function, not for users"],
        ['checkconfig', None, CheckConfigOptions,
         "test the validity of a master.cfg config file"],
        ['user', None, UserOptions,
         "Manage users in buildbot's database"],
        ['dataspec', None, DataSpecOption,
         "Output data api spec"],
        ['processwwwindex', None, ProcessWWWIndexOption,
         "Process the index.html to enable the front end package working without backend. "
         "This is a command to work with the frontend's proxy task."
         ],
        ['cleanupdb', None, CleanupDBOptions,
         "cleanup the database"
         ]
    ]

    def opt_version(self):
        import buildbot
        print("Buildbot version: %s" % buildbot.version)
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
        config.parseOptions(sys.argv[1:])
    except usage.error as e:
        print("%s:  %s" % (sys.argv[0], e))
        print()

        c = getattr(config, 'subOptions', config)
        print(str(c))
        sys.exit(1)

    subconfig = config.subOptions
    subcommandFunction = reflect.namedObject(subconfig.subcommandFunction)
    sys.exit(subcommandFunction(subconfig))
