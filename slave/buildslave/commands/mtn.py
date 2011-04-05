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

from twisted.python import log
from twisted.internet import defer

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
#from buildslave.util import remove_userpassword

class MonotoneError(Exception):
    """Error class for this module."""


class Monotone(SourceBaseCommand):
    """Monotone specific VC operation. In addition to the arguments
    handled by SourceBaseCommand, this command reads the following keys:

    ['repourl'] (required):     the Monotone repository string
    ['branch'] (required):      which branch to retrieve.

    ['revision'] (optional):    which revision (revision selector)
                                to retrieve.
    ['progress'] (optional):       have mtn output progress markers,
                                   avoiding timeouts for long fetches;
    """

    header = "monotone operation"

    def setup(self, args):
        SourceBaseCommand.setup(self, args)

        self.repourl = args['repourl']
        self.branch = args['branch']
        
        self.revision = args.get('revision', None)
        self.progress = args.get('progress', False)

        self._pull_timeout = args.get("timeout")

        self.sourcedata = "%s?%s" % (self.repourl, self.branch)
        self.stdout = ""
        self.stderr = ""
        self.database = os.path.join(self.builder.basedir, 'db.mtn')
        self.mtn = self.getCommand("mtn")

    def start(self):
        def cont(res):
            # Continue with start() method in superclass.
            return SourceBaseCommand.start(self)

        d = self._checkDb();
        d.addCallback(cont)
        return d

    def doVCUpdate(self):
        return self._dovccmd(self._update, True)

    def doVCFull(self):
        return self._dovccmd(self._checkout, True)

    def _fullSrcdir(self):
        return os.path.join(self.builder.basedir, self.srcdir)

    def sourcedirIsUpdateable(self):
        return os.path.isdir(os.path.join(self._fullSrcdir(), "_MTN"))

    def _dovccmd(self, fn, dopull, cb=None, **kwargs):
        if dopull:
            command = [self.mtn, 'pull', self.sourcedata,
                       '--db', self.database]
            if self.progress:
                command.extend(['--ticker=dot'])
            else:
                command.extend(['--ticker=none'])
            c = runprocess.RunProcess(self.builder, command,
                                      self.builder.basedir,
                                      environ=self.env, sendRC=False,
                                      timeout=self.timeout,
                                      maxTime=self.maxTime,
                                      keepStdout=True, usePTY=False)
            self.sendStatus({"header": "pulling %s from %s\n"
                             % (self.branch, self.sourcedata)})
            self.command = c
            d = c.start()
            d.addCallback(self._abandonOnFailure)
            d.addCallback(fn)
        else:
            d = fn(None)
        if cb:
            d.addCallback(cb)
        return d

    def _update(self, res):
        command = [self.mtn, 'update',
                   '--db', self.database]
        if self.revision:
            command.extend(['--revision', self.revision])
        else:
            command.extend(["-r", "h:" + self.branch])
        command.extend(["-b", self.branch])
        c = runprocess.RunProcess(self.builder, command, self._fullSrcdir(),
                                  environ=self.env, sendRC=False,
                                  timeout=self.timeout, maxTime=self.maxTime,
                                  keepStdout=True, usePTY=False)
        d = c.start()
        return d

    def _checkout(self, res):
        command = [self.mtn, 'checkout', self._fullSrcdir(),
                   '--db', self.database]
        if self.revision:
            command.extend(['--revision', self.revision])
        command.extend(['--branch', self.branch])
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                                  environ=self.env, sendRC=False,
                                  timeout=self.timeout, maxTime=self.maxTime,
                                  keepStdout=True, usePTY=False)
        d = c.start()
        return d

    def _checkDb(self):
        # Don't send stderr. When there is no database, this might confuse
        # users, as they will see a mtn error message. But having no database
        # repo is not an error, just an indication that we need to pull one.
        c = runprocess.RunProcess(self.builder, [self.mtn, 'db', 'info',
                                                 '--db', self.database],
                                  self.builder.basedir,
                                  environ=self.env, sendRC=False,
                                  keepStdout=True, sendStderr=False,
                                  usePTY=False)
        d = c.start()
        def afterCheckRepo(res, cdi):
            if type(res) is int and res != 0:
                log.msg("No database found, creating it")
                # mtn info fails, try to create shared repo.
                # We'll be doing an initial pull, so up the timeout to
                # 3 hours to make sure it will have time to complete.
                self._pull_timeout = max(self._pull_timeout, 3 * 60 * 60)
                c = runprocess.RunProcess(self.builder, [self.mtn, 'db', 'init',
                                                         '--db', self.database],
                                          self.builder.basedir,
                                          environ=self.env, 
                                          sendRC=False, usePTY=False)
                self.command = c
                return c.start()
            elif cdi.stdout.find("(migration needed)") > 0:
                log.msg("Older format database found, migrating it")
                # mtn info fails, try to create shared repo.
                c = runprocess.RunProcess(self.builder, [self.mtn,
                                                         'db', 'migrate',
                                                         '--db', self.database],
                                          self.builder.basedir,
                                          environ=self.env, 
                                          sendRC=False, usePTY=False)
                self.command = c
                return c.start()
            elif cdi.stdout.find("(too new, cannot use)") > 0:
                raise MonotoneError, "The database is of a newer format than mtn can handle...  Abort!"
            else:
                return defer.succeed(res)
        d.addCallback(afterCheckRepo, c)
        return d

    def parseGotRevision(self):
        def _parse(res):
            hash = self.command.stdout.strip()
            if len(hash) != 40:
                return None
            return hash
        return self._dovccmd(self._get_base_revision, False, _parse)

    def _get_base_revision(self, res):
        c = runprocess.RunProcess(self.builder,
                                  [self.mtn, 'automate', 'select', 'w:'],
                                  self._fullSrcdir(),
                                  sendRC=False,
                                  timeout=self.timeout, maxTime=self.maxTime,
                                  keepStdout=True, usePTY=False)
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d
