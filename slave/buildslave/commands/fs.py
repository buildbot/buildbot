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

    header = "rmdir"

    def setup(self,args):
        self.logEnviron = args.get('logEnviron',True)


    @defer.deferredGenerator
    def start(self):
        args = self.args
        # args['dir'] is relative to Builder directory, and is required.
        assert args['dir'] is not None
        dirnames = args['dir']

        self.timeout = args.get('timeout', 120)
        self.maxTime = args.get('maxTime', None)
        self.rc = 0
        if type(dirnames) is list:
            assert len(dirnames) != 0
            for dirname in dirnames:
                wfd = defer.waitForDeferred(self.removeSingleDir(dirname))
                yield wfd
                res = wfd.getResult()
                # Even if single removal of single file/dir consider it as
                # failure of whole command, but continue removing other files
                # Send 'rc' to master to handle failure cases
                if res != 0:
                    self.rc = res
        else:
            wfd = defer.waitForDeferred(self.removeSingleDir(dirnames))
            yield wfd
            self.rc = wfd.getResult()

        self.sendStatus({'rc': self.rc})

    def removeSingleDir(self, dirname):
        # TODO: remove the old tree in the background
        self.dir = os.path.join(self.builder.basedir, dirname)
        if runtime.platformType != "posix":
            # if we're running on w32, use rmtree instead. It will block,
            # but hopefully it won't take too long.
            utils.rmdirRecursive(self.dir)
            d = defer.succeed(0)
        else:
            d = self._clobber(None)

        return d

    def _clobber(self, dummy, chmodDone = False):
        command = ["rm", "-rf", self.dir]
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                         logEnviron=self.logEnviron, usePTY=False)

        self.command = c
        # sendRC=0 means the rm command will send stdout/stderr to the
        # master, but not the rc=0 when it finishes. That job is left to
        # _sendRC
        d = c.start()
        # The rm -rf may fail if there is a left-over subdir with chmod 000
        # permissions. So if we get a failure, we attempt to chmod suitable
        # permissions and re-try the rm -rf.
        if not chmodDone:
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
                         logEnviron=self.logEnviron, usePTY=False)

        self.command = c
        d = c.start()
        d.addCallback(lambda dummy: self._clobber(dummy, True))
        return d

class CopyDirectory(base.Command):

    header = "cpdir"

    def setup(self,args):
        self.logEnviron = args.get('logEnviron',True)
        
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
                             logEnviron=self.logEnviron, usePTY=False)
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)

        # always set the RC, regardless of platform
        d.addCallbacks(self._sendRC, self._checkAbandoned)
        return d

class StatFile(base.Command):

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
