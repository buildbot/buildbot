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

from __future__ import absolute_import
from __future__ import print_function

import glob
import os
import platform
import shutil
import sys

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import runtime

from buildbot_worker import runprocess
from buildbot_worker.commands import base
from buildbot_worker.commands import utils


class MakeDirectory(base.Command):

    header = "mkdir"

    # args['paths'] specifies the absolute paths of directories to create
    requiredArgs = ['paths']

    def start(self):
        paths = self.args['paths']

        for dirname in paths:
            try:
                if not os.path.isdir(dirname):
                    os.makedirs(dirname)
            except OSError as e:
                self.log_msg("MakeDirectory {0} failed: {1}".format(dirname, e))
                self.sendStatus([
                    ('header', '{0}: {1}: {2}'.format(self.header, e.strerror, dirname)),
                    ('rc', e.errno)
                ])
                return
        self.sendStatus([('rc', 0)])


class RemoveDirectory(base.Command):

    header = "rmdir"

    # args['paths'] specifies the absolute paths of directories or files to remove
    requiredArgs = ['paths']

    def setup(self, args):
        self.logEnviron = args.get('logEnviron', True)

    @defer.inlineCallbacks
    def start(self):
        args = self.args
        dirnames = args['paths']

        self.timeout = args.get('timeout', 120)
        self.maxTime = args.get('maxTime', None)
        self.rc = 0

        assert dirnames
        for path in dirnames:
            res = yield self.removeSingleDir(path)
            # Even if single removal of single file/dir consider it as
            # failure of whole command, but continue removing other files
            # Send 'rc' to master to handle failure cases
            if res != 0:
                self.rc = res

        self.sendStatus([('rc', self.rc)])

    def removeSingleDir(self, path):
        if runtime.platformType != "posix":
            d = threads.deferToThread(utils.rmdirRecursive, path)

            def cb(_):
                return 0  # rc=0

            def eb(f):
                self.sendStatus([
                    ('header', 'exception from rmdirRecursive\n' + f.getTraceback())
                ])
                return -1  # rc=-1
            d.addCallbacks(cb, eb)
        else:
            d = self._clobber(None, path)

        return d

    @defer.inlineCallbacks
    def _clobber(self, dummy, path, chmodDone=False):
        command = ["rm", "-rf", path]

        c = runprocess.RunProcess(self.command_id, command, self.protocol_command.worker_basedir,
                                  self.protocol_command.unicode_encoding,
                                  self.protocol_command.send_update,
                                  sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                                  logEnviron=self.logEnviron, usePTY=False)

        self.command = c
        # sendRC=0 means the rm command will send stdout/stderr to the
        # master, but not the rc=0 when it finishes. That job is left to
        # _sendRC
        rc = yield c.start()
        # The rm -rf may fail if there is a left-over subdir with chmod 000
        # permissions. So if we get a failure, we attempt to chmod suitable
        # permissions and re-try the rm -rf.
        if not chmodDone:
            rc = yield self._tryChmod(rc, path)
        defer.returnValue(rc)

    @defer.inlineCallbacks
    def _tryChmod(self, rc, path):
        assert isinstance(rc, int)
        if rc == 0:
            defer.returnValue(0)
            return  # pragma: no cover
        # Attempt a recursive chmod and re-try the rm -rf after.

        command = ["chmod", "-Rf", "u+rwx", path]
        if sys.platform.startswith('freebsd'):
            # Work around a broken 'chmod -R' on FreeBSD (it tries to recurse into a
            # directory for which it doesn't have permission, before changing that
            # permission) by running 'find' instead
            command = ["find", path, '-exec', 'chmod', 'u+rwx', '{}', ';']

        c = runprocess.RunProcess(self.command_id, command, self.protocol_command.worker_basedir,
                                  self.protocol_command.unicode_encoding,
                                  self.protocol_command.send_update,
                                  sendRC=0, timeout=self.timeout, maxTime=self.maxTime,
                                  logEnviron=self.logEnviron, usePTY=False)

        self.command = c
        rc = yield c.start()
        rc = yield self._clobber(rc, path, True)
        defer.returnValue(rc)


class CopyDirectory(base.Command):

    header = "cpdir"

    # args['to_path'] and args['from_path'] are relative to Builder directory, and
    # are required.
    requiredArgs = ['to_path', 'from_path']

    def setup(self, args):
        self.logEnviron = args.get('logEnviron', True)

    def start(self):
        args = self.args

        from_path = self.args['from_path']
        to_path = self.args['to_path']

        self.timeout = args.get('timeout', 120)
        self.maxTime = args.get('maxTime', None)

        if runtime.platformType != "posix":
            d = threads.deferToThread(shutil.copytree, from_path, to_path)

            def cb(_):
                return 0  # rc=0

            def eb(f):
                self.sendStatus([('header', 'exception from copytree\n' + f.getTraceback())])
                return -1  # rc=-1
            d.addCallbacks(cb, eb)

            @d.addCallback
            def send_rc(rc):
                self.sendStatus([('rc', rc)])
        else:
            if not os.path.exists(os.path.dirname(to_path)):
                os.makedirs(os.path.dirname(to_path))
            if os.path.exists(to_path):
                # I don't think this happens, but just in case..
                self.log_msg(("cp target '{0}' already exists -- cp will not do what you think!"
                              ).format(to_path))

            if platform.system().lower().find('solaris') >= 0:
                command = ['cp', '-R', '-P', '-p', from_path, to_path]
            else:
                command = ['cp', '-R', '-P', '-p', '-v', from_path, to_path]

            c = runprocess.RunProcess(self.command_id, command,
                                      self.protocol_command.worker_basedir,
                                      self.protocol_command.unicode_encoding,
                                      self.protocol_command.send_update,
                                      sendRC=False, timeout=self.timeout,
                                      maxTime=self.maxTime, logEnviron=self.logEnviron,
                                      usePTY=False)
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)

            d.addCallbacks(self._sendRC, self._checkAbandoned)
        return d


class StatFile(base.Command):

    header = "stat"

    # args['path'] absolute path of a file
    requireArgs = ['path']

    def start(self):
        filename = self.args['path']

        try:
            stat = os.stat(filename)
            self.sendStatus([('stat', tuple(stat)), ('rc', 0)])
        except OSError as e:
            self.log_msg("StatFile {0} failed: {1}".format(filename, e))
            self.sendStatus([
                ('header', '{0}: {1}: {2}'.format(self.header, e.strerror, filename)),
                ('rc', e.errno)
            ])


class GlobPath(base.Command):

    header = "glob"

    # args['path'] shell-style path specification of a pattern
    requiredArgs = ['path']

    def start(self):
        pathname = self.args['path']

        try:
            # recursive matching is only support in python3.5+
            if sys.version_info[:2] >= (3, 5):
                files = glob.glob(pathname, recursive=True)
            else:
                files = glob.glob(pathname)
            self.sendStatus([('files', files), ('rc', 0)])
        except OSError as e:
            self.log_msg("GlobPath {0} failed: {1}".format(pathname, e))
            self.sendStatus([
                ('header', '{0}: {1}: {2}'.format(self.header, e.strerror, pathname)),
                ('rc', e.errno)
            ])


class ListDir(base.Command):

    header = "listdir"

    # args['path'] absolute path of the directory to list
    requireArgs = ['path']

    def start(self):
        dirname = self.args['path']

        try:
            files = os.listdir(dirname)
            self.sendStatus([('files', files), ('rc', 0)])
        except OSError as e:
            self.log_msg("ListDir {0} failed: {1}".format(dirname, e))
            self.sendStatus([
                ('header', '{0}: {1}: {2}'.format(self.header, e.strerror, dirname)),
                ('rc', e.errno)
            ])


class RemoveFile(base.Command):

    header = "rmfile"

    # args['path'] absolute path of a file to delete
    requiredArgs = ['path']

    def start(self):
        pathname = self.args['path']

        try:
            os.remove(pathname)
            self.sendStatus([('rc', 0)])
        except OSError as e:
            self.log_msg("remove file {0} failed: {1}".format(pathname, e))
            self.sendStatus([
                ('header', '{0}: {1}: {2}'.format(self.header, e.strerror, pathname)),
                ('rc', e.errno)
            ])
