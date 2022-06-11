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

import copy
import errno
import os
import stat
import sys
import traceback
from contextlib import contextmanager

from twisted.python import runtime
from twisted.python import usage

from buildbot.config.errors import ConfigErrors
from buildbot.config.master import FileLoader


@contextmanager
def captureErrors(errors, msg):
    try:
        yield
    except errors as e:
        print(msg)
        print(e)
        return 1
    return None


class BusyError(RuntimeError):
    pass


def checkPidFile(pidfile):
    """ mostly comes from _twistd_unix.py which is not twisted public API :-/

        except it returns an exception instead of exiting
    """
    if os.path.exists(pidfile):
        try:
            with open(pidfile, encoding='utf-8') as f:
                pid = int(f.read())
        except ValueError as e:
            raise ValueError(f'Pidfile {pidfile} contains non-numeric value') from e
        try:
            os.kill(pid, 0)
        except OSError as why:
            if why.errno == errno.ESRCH:
                # The pid doesn't exist.
                print(f'Removing stale pidfile {pidfile}')
                os.remove(pidfile)
            else:
                raise OSError(
                    f"Can't check status of PID {pid} from pidfile {pidfile}: {why}") from why
        else:
            raise BusyError(f"'{pidfile}' exists - is this master still running?")


def checkBasedir(config):
    if not config['quiet']:
        print("checking basedir")

    if not isBuildmasterDir(config['basedir']):
        return False

    if runtime.platformType != 'win32':  # no pids on win32
        if not config['quiet']:
            print("checking for running master")

        pidfile = os.path.join(config['basedir'], 'twistd.pid')
        try:
            checkPidFile(pidfile)
        except Exception as e:
            print(str(e))
            return False

    tac = getConfigFromTac(config['basedir'])
    if tac:
        if isinstance(tac.get('rotateLength', 0), str):
            print("ERROR: rotateLength is a string, it should be a number")
            print("ERROR: Please, edit your buildbot.tac file and run again")
            print(
                "ERROR: See http://trac.buildbot.net/ticket/2588 for more details")
            return False
        if isinstance(tac.get('maxRotatedFiles', 0), str):
            print("ERROR: maxRotatedFiles is a string, it should be a number")
            print("ERROR: Please, edit your buildbot.tac file and run again")
            print(
                "ERROR: See http://trac.buildbot.net/ticket/2588 for more details")
            return False

    return True


def loadConfig(config, configFileName='master.cfg'):
    if not config['quiet']:
        print(f"checking {configFileName}")

    try:
        master_cfg = FileLoader(config['basedir'], configFileName).loadConfig()
    except ConfigErrors as e:
        print("Errors loading configuration:")

        for msg in e.errors:
            print("  " + msg)
        return None
    except Exception:
        print("Errors loading configuration:")
        traceback.print_exc(file=sys.stdout)
        return None

    return master_cfg


def isBuildmasterDir(dir):
    def print_error(error_message):
        print(f"{error_message}\ninvalid buildmaster directory '{dir}'")

    buildbot_tac = os.path.join(dir, "buildbot.tac")
    try:
        with open(buildbot_tac, encoding='utf-8') as f:
            contents = f.read()
    except IOError as exception:
        print_error(f"error reading '{buildbot_tac}': {exception.strerror}")
        return False

    if "Application('buildmaster')" not in contents:
        print_error(f"unexpected content in '{buildbot_tac}'")
        return False

    return True


def getConfigFromTac(basedir, quiet=False):
    tacFile = os.path.join(basedir, 'buildbot.tac')
    if os.path.exists(tacFile):
        # don't mess with the global namespace, but set __file__ for
        # relocatable buildmasters
        tacGlobals = {'__file__': tacFile}
        try:
            with open(tacFile, encoding='utf-8') as f:
                exec(f.read(), tacGlobals)  # pylint: disable=exec-used
        except Exception:
            if not quiet:
                traceback.print_exc()
            raise
        return tacGlobals
    return None


def getConfigFileFromTac(basedir, quiet=False):
    # execute the .tac file to see if its configfile location exists
    config = getConfigFromTac(basedir, quiet=quiet)
    if config:
        return config.get("configfile", "master.cfg")
    return "master.cfg"


class SubcommandOptions(usage.Options):
    # subclasses should set this to a list-of-lists in order to source the
    # .buildbot/options file.  Note that this *only* works with optParameters,
    # not optFlags.  Example:
    # buildbotOptions = [ [ 'optfile-name', 'parameter-name' ], .. ]
    buildbotOptions = None

    # set this to options that must have non-None values
    requiredOptions = []

    def __init__(self, *args):
        # for options in self.buildbotOptions, optParameters, and the options
        # file, change the default in optParameters to the value in the options
        # file, call through to the constructor, and then change it back.
        # Options uses reflect.accumulateClassList, so this *must* be a class
        # attribute; however, we do not want to permanently change the class.
        # So we patch it temporarily and restore it after.
        cls = self.__class__
        if hasattr(cls, 'optParameters'):
            old_optParameters = cls.optParameters
            cls.optParameters = op = copy.deepcopy(cls.optParameters)
            if self.buildbotOptions:
                optfile = self.optionsFile = self.loadOptionsFile()
                # pylint: disable=not-an-iterable
                for optfile_name, option_name in self.buildbotOptions:
                    for i, val in enumerate(op):
                        if (val[0] == option_name and
                                optfile_name in optfile):
                            op[i] = list(val)
                            op[i][2] = optfile[optfile_name]
        super().__init__(*args)
        if hasattr(cls, 'optParameters'):
            cls.optParameters = old_optParameters

    def loadOptionsFile(self, _here=None):
        """Find the .buildbot/options file. Crawl from the current directory
        up towards the root, and also look in ~/.buildbot . The first directory
        that's owned by the user and has the file we're looking for wins.
        Windows skips the owned-by-user test.

        @rtype:  dict
        @return: a dictionary of names defined in the options file. If no
            options file was found, return an empty dict.
        """

        here = _here or os.path.abspath(os.getcwd())

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
                break  # we've hit the root
            here = next
            toomany -= 1  # just in case
            if toomany == 0:
                print("I seem to have wandered up into the infinite glories "
                      "of the heavens. Oops.")
                break

        searchpath.append(home)

        localDict = {}

        for d in searchpath:
            if os.path.isdir(d):
                if runtime.platformType != 'win32':
                    if os.stat(d)[stat.ST_UID] != os.getuid():
                        print(f"skipping {d} because you don't own it")
                        continue  # security, skip other people's directories
                optfile = os.path.join(d, "options")
                if os.path.exists(optfile):
                    try:
                        with open(optfile, "r", encoding='utf-8') as f:
                            options = f.read()
                        exec(options, localDict)  # pylint: disable=exec-used
                    except Exception:
                        print(f"error while reading {optfile}")
                        raise
                    break

        for k in list(localDict.keys()):  # pylint: disable=consider-iterating-dictionary
            if k.startswith("__"):
                del localDict[k]
        return localDict

    def postOptions(self):
        missing = [k for k in self.requiredOptions if self[k] is None]
        if missing:
            if len(missing) > 1:
                msg = 'Required arguments missing: ' + ', '.join(missing)
            else:
                msg = 'Required argument missing: ' + missing[0]
            raise usage.UsageError(msg)


class BasedirMixin:

    """SubcommandOptions Mixin to handle subcommands that take a basedir
    argument"""

    # on tab completion, suggest directories as first argument
    if hasattr(usage, 'Completions'):
        # only set completion suggestion if running with
        # twisted version (>=11.1.0) that supports it
        compData = usage.Completions(
            extraActions=[usage.CompleteDirs(descr="buildbot base directory")])

    def parseArgs(self, *args):
        if args:
            self['basedir'] = args[0]
        else:
            # Use the current directory if no basedir was specified.
            self['basedir'] = os.getcwd()
        if len(args) > 1:
            raise usage.UsageError("I wasn't expecting so many arguments")

    def postOptions(self):
        # get an unambiguous, expanded basedir, including expanding '~', which
        # may be useful in a .buildbot/config file
        self['basedir'] = os.path.abspath(os.path.expanduser(self['basedir']))
