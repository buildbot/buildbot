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

from __future__ import with_statement

import copy
import os
import stat

from twisted.python import runtime
from twisted.python import usage


def isBuildmasterDir(dir):
    def print_error(error_message):
        print "%s\ninvalid buildmaster directory '%s'" % (error_message, dir)

    buildbot_tac = os.path.join(dir, "buildbot.tac")
    try:
        contents = open(buildbot_tac).read()
    except IOError, exception:
        print_error("error reading '%s': %s" %
                    (buildbot_tac, exception.strerror))
        return False

    if "Application('buildmaster')" not in contents:
        print_error("unexpected content in '%s'" % buildbot_tac)
        return False

    return True


def getConfigFromTac(basedir):
    tacFile = os.path.join(basedir, 'buildbot.tac')
    if os.path.exists(tacFile):
        # don't mess with the global namespace, but set __file__ for relocatable buildmasters
        tacGlobals = {'__file__': tacFile}
        execfile(tacFile, tacGlobals)
        return tacGlobals
    return None


def getConfigFileFromTac(basedir):
    # execute the .tac file to see if its configfile location exists
    config = getConfigFromTac(basedir)
    if config:
        return config.get("configfile", "master.cfg")
    else:
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
                for optfile_name, option_name in self.buildbotOptions:
                    for i in range(len(op)):
                        if (op[i][0] == option_name
                                and optfile_name in optfile):
                            op[i] = list(op[i])
                            op[i][2] = optfile[optfile_name]
        usage.Options.__init__(self, *args)
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
                print ("I seem to have wandered up into the infinite glories "
                       "of the heavens. Oops.")
                break

        searchpath.append(home)

        localDict = {}

        for d in searchpath:
            if os.path.isdir(d):
                if runtime.platformType != 'win32':
                    if os.stat(d)[stat.ST_UID] != os.getuid():
                        print "skipping %s because you don't own it" % d
                        continue  # security, skip other people's directories
                optfile = os.path.join(d, "options")
                if os.path.exists(optfile):
                    try:
                        with open(optfile, "r") as f:
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

    def postOptions(self):
        missing = [k for k in self.requiredOptions if self[k] is None]
        if missing:
            if len(missing) > 1:
                msg = 'Required arguments missing: ' + ', '.join(missing)
            else:
                msg = 'Required argument missing: ' + missing[0]
            raise usage.UsageError(msg)


class BasedirMixin(object):

    """SubcommandOptions Mixin to handle subcommands that take a basedir
    argument"""

    # on tab completion, suggest directories as first argument
    if hasattr(usage, 'Completions'):
        # only set completion suggestion if running with
        # twisted version (>=11.1.0) that supports it
        compData = usage.Completions(
            extraActions=[usage.CompleteDirs(descr="buildbot base directory")])

    def parseArgs(self, *args):
        if len(args) > 0:
            self['basedir'] = args[0]
        else:
            # Use the current directory if no basedir was specified.
            self['basedir'] = os.getcwd()
        if len(args) > 1:
            raise usage.UsageError("I wasn't expecting so many arguments")

    def postOptions(self):
        # get an unambiguous, epxnaed basedir, including expanding '~', which
        # may be useful in a .buildbot/config file
        self['basedir'] = os.path.abspath(os.path.expanduser(self['basedir']))
