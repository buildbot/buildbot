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

import os
import sys
import shutil

from twisted.internet import defer
from twisted.python import runtime, log

from buildslave import runprocess
from buildslave.commands import base, utils

class MakeDirectory(base.Command):
    """This is a Command which creates a directory. The args dict contains
    the following keys:

        - ['dir'] (required): subdirectory which the command will create,
                                  relative to the builder dir

    MakeDirectory creates the following status messages:
        - {'rc': rc} : when the process has terminated
    """

    header = "mkdir"

    def start(self):
        args = self.args
        # args['dir'] is relative to Builder directory, and is required.
        assert args['dir'] is not None
        dirname = os.path.join(self.builder.basedir, args['dir'])

        try:
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            self.sendStatus({'rc': 0})
        except:
            self.sendStatus({'rc': 1})

class RemoveDirectory(base.Command):
    """This is a Command which removes a directory. The args dict contains
    the following keys:

        - ['dir'] (required): subdirectory which the command will create,
                                  relative to the builder dir

        - ['timeout']:  seconds of silence tolerated before we kill off the
                        command

        - ['maxTime']:  seconds before we kill off the command


    RemoveDirectory creates the following status messages:
        - {'rc': rc} : when the process has terminated
    """

    header = "rmdir"

    def start(self):
        args = self.args
        # args['dir'] is relative to Builder directory, and is required.
        assert args['dir'] is not None
        dirname = args['dir']

        self.timeout = args.get('timeout', 120)
        self.maxTime = args.get('maxTime', None)

        # TODO: remove the old tree in the background
        self.dir = os.path.join(self.builder.basedir, dirname)
        if runtime.platformType != "posix":
            # if we're running on w32, use rmtree instead. It will block,
            # but hopefully it won't take too long.
            utils.rmdirRecursive(self.dir)
            d = defer.succeed(0)
        else:
            d = self._clobber(None)

        # always add the RC, regardless of platform
        d.addCallbacks(self._sendRC, self._checkAbandoned)
        return d

    def _clobber(self, dummy, chmodDone = False):
        command = ["rm", "-rf", self.dir]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                         usePTY=False)

        self.command = c
        # sendRC=0 means the rm command will send stdout/stderr to the
        # master, but not the rc=0 when it finishes. That job is left to
        # _sendRC
        d = c.start()
        # The rm -rf may fail if there is a left-over subdir with chmod 000
        # permissions. So if we get a failure, we attempt to chmod suitable
        # permissions and re-try the rm -rf.
        if chmodDone:
            d.addCallback(self._abandonOnFailure)
        else:
            d.addCallback(self._tryChmod)
        return d

    def _tryChmod(self, rc):
        assert isinstance(rc, int)
        if rc == 0:
            return defer.succeed(0)
        # Attempt a recursive chmod and re-try the rm -rf after.

        command = ["chmod", "-Rf", "u+rwx", os.path.join(self.builder.basedir, self.dir)]
        if sys.platform.startswith('freebsd'):
            # Work around a broken 'chmod -R' on FreeBSD (it tries to recurse into a
            # directory for which it doesn't have permission, before changing that
            # permission) by running 'find' instead
            command = ["find", os.path.join(self.builder.basedir, self.dir),
                                '-exec', 'chmod', 'u+rwx', '{}', ';' ]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                         usePTY=False)

        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(lambda dummy: self._clobber(dummy, True))
        return d

class CopyDirectory(base.Command):
    """This is a Command which copies a directory. The args dict contains
    the following keys:

        - ['fromdir'] (required): subdirectory which the command will copy,
                                  relative to the builder dir
        - ['todir'] (required): subdirectory which the command will create,
                                  relative to the builder dir

        - ['timeout']:  seconds of silence tolerated before we kill off the
                        command

        - ['maxTime']:  seconds before we kill off the command


    CopyDirectory creates the following status messages:
        - {'rc': rc} : when the process has terminated
    """

    header = "rmdir"

    def start(self):
        args = self.args
        # args['todir'] is relative to Builder directory, and is required.
        # args['fromdir'] is relative to Builder directory, and is required.
        assert args['todir'] is not None
        assert args['fromdir'] is not None

        fromdir = os.path.join(self.builder.basedir, args['fromdir'])
        todir = os.path.join(self.builder.basedir, args['todir'])

        self.timeout = args.get('timeout', 120)
        self.maxTime = args.get('maxTime', None)

        if runtime.platformType != "posix":
            self.sendStatus({'header': "Since we're on a non-POSIX platform, "
            "we're not going to try to execute cp in a subprocess, but instead "
            "use shutil.copytree(), which will block until it is complete.  "
            "fromdir: %s, todir: %s\n" % (fromdir, todir)})
            shutil.copytree(fromdir, todir)
            d = defer.succeed(0)
        else:
            if not os.path.exists(os.path.dirname(todir)):
                os.makedirs(os.path.dirname(todir))
            if os.path.exists(todir):
                # I don't think this happens, but just in case..
                log.msg("cp target '%s' already exists -- cp will not do what you think!" % todir)

            command = ['cp', '-R', '-P', '-p', fromdir, todir]
            c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                             sendRC=False, timeout=self.timeout, maxTime=self.maxTime,
                             usePTY=False)
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)

        # always set the RC, regardless of platform
        d.addCallbacks(self._sendRC, self._checkAbandoned)
        return d

class StatFile(base.Command):
    """This is a command which stats a file on the slave. The args dict contains the following keys:

        - ['file'] (required): file to stat

    StatFile creates the following status messages:
        - {'rc': rc} : 0 if the file is found, 1 otherwise
        - {'stat': stat} : if the files is found, stat contains the result of os.stat
    """

    header = "stat"

    def start(self):
        args = self.args
        # args['dir'] is relative to Builder directory, and is required.
        assert args['file'] is not None
        filename = os.path.join(self.builder.basedir, args['file'])

        try:
            stat = os.stat(filename)
            self.sendStatus({'stat': tuple(stat)})
            self.sendStatus({'rc': 0})
        except:
            self.sendStatus({'rc': 1})
