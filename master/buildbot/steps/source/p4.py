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
# Portions Copyright 2013 Bad Dog Consulting

import re

from buildbot import config
from buildbot import interfaces
from buildbot.interfaces import BuildSlaveTooOldError
from buildbot.process import buildstep
from buildbot.process.properties import Interpolate
from buildbot.steps.source import Source
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from types import StringType


# Notes:
#  see
# http://perforce.com/perforce/doc.current/manuals/cmdref/o.gopts.html#1040647
#   for getting p4 command to output marshalled python dictionaries as output
#   for commands.
#   Perhaps switch to using 'p4 -G' :  From URL above:
#   -G Causes all output (and batch input for form commands with -i) to be
#   formatted as marshalled Python dictionary objects. This is most often used
#   when scripting.

debug_logging = False


class P4(Source):

    """Perform Perforce checkout/update operations."""

    name = 'p4'

    renderables = ['mode', 'p4base', 'p4client', 'p4viewspec', 'p4branch']
    possible_modes = ('incremental', 'full')

    def __init__(self, mode='incremental',
                 method=None, p4base=None, p4branch=None,
                 p4port=None, p4user=None,
                 p4passwd=None, p4extra_views=(), p4line_end='local',
                 p4viewspec=None, p4viewspec_suffix='...',
                 p4client=Interpolate('buildbot_%(prop:slavename)s_%(prop:buildername)s'),
                 p4client_spec_options='allwrite rmdir',
                 p4extra_args=None,
                 p4bin='p4',
                 use_tickets=False,
                 **kwargs):
        self.method = method
        self.mode = mode
        self.p4branch = p4branch
        self.p4bin = p4bin
        self.p4base = p4base
        self.p4port = p4port
        self.p4user = p4user
        self.p4passwd = p4passwd
        self.p4extra_views = p4extra_views
        self.p4viewspec = p4viewspec
        self.p4viewspec_suffix = p4viewspec_suffix
        self.p4line_end = p4line_end
        self.p4client = p4client
        self.p4client_spec_options = p4client_spec_options
        self.p4extra_args = p4extra_args
        self.use_tickets = use_tickets

        Source.__init__(self, **kwargs)

        if self.mode not in self.possible_modes and not interfaces.IRenderable.providedBy(self.mode):
            config.error("mode %s is not an IRenderable, or one of %s" % (self.mode, self.possible_modes))

        if not p4viewspec and p4base is None:
            config.error("You must provide p4base or p4viewspec")

        if p4viewspec and (p4base or p4branch or p4extra_views):
            config.error("Either provide p4viewspec or p4base and p4branch (and optionally p4extra_views")

        if p4viewspec and isinstance(p4viewspec, StringType):
            config.error("p4viewspec must not be a string, and should be a sequence of 2 element sequences")

        if not interfaces.IRenderable.providedBy(p4base) and p4base and p4base.endswith('/'):
            config.error('p4base should not end with a trailing / [p4base = %s]' % p4base)

        if not interfaces.IRenderable.providedBy(p4branch) and p4branch and p4branch.endswith('/'):
            config.error('p4branch should not end with a trailing / [p4branch = %s]' % p4branch)

        if (p4branch or p4extra_views) and not p4base:
            config.error('If you specify either p4branch or p4extra_views you must also specify p4base')

        if self.p4client_spec_options is None:
            self.p4client_spec_options = ''

    def startVC(self, branch, revision, patch):
        if debug_logging:
            log.msg('in startVC')

        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = self.addLogForRemoteCommands("stdio")

        d = self.checkP4()

        def checkInstall(p4Installed):
            if not p4Installed:
                raise BuildSlaveTooOldError("p4 is not installed on slave")
            return 0
        d.addCallback(checkInstall)

        if self.use_tickets and self.p4passwd:
            d.addCallback(self._acquireTicket)

        if self.mode == 'full':
            d.addCallback(self.full)
        elif self.mode == 'incremental':
            d.addCallback(self.incremental)

        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.inlineCallbacks
    def full(self, _):
        if debug_logging:
            log.msg("P4:full()..")

        # First we need to create the client
        yield self._createClientSpec()

        # Then p4 sync #none
        yield self._sync(['#none'])

        # Then remove directory.
        yield self.runRmdir(self.workdir)

        # Then we need to sync the client
        if self.revision:
            if debug_logging:
                log.msg("P4: full() sync command based on :base:%s changeset:%d", self._getP4BaseForLog(), int(self.revision))
            yield self._sync(['%s...@%d' % (self._getP4BaseForCommand(), int(self.revision))])
        else:
            if debug_logging:
                log.msg("P4: full() sync command based on :base:%s no revision", self._getP4BaseForLog())
            yield self._sync([])

        if debug_logging:
            log.msg("P4: full() sync done.")

    @defer.inlineCallbacks
    def incremental(self, _):
        if debug_logging:
            log.msg("P4:incremental()")

        # First we need to create the client
        yield self._createClientSpec()

        # and plan to do a checkout
        args = []
        if self.revision:
            args.extend(['%s...@%d' % (self._getP4BaseForCommand(), int(self.revision))])

        if debug_logging:
            log.msg("P4:incremental() args:%s revision:%s", args, self.revision)
        yield self._sync(args)

    def _sync(self, args):
        abandonOnFailure = (self.retry[1] <= 0) if self.retry else True
        d = self._dovccmd(['sync'] + args,
                          abandonOnFailure=abandonOnFailure)

        def _retry(res):
            if self.stopped or res == 0:
                return res
            delay, repeats = self.retry
            if repeats > 0:
                log.msg("Sync failed, trying %d more times after %d seconds"
                        % (repeats, delay))
                self.retry = (delay, repeats - 1)
                df = defer.Deferred()
                df.addCallback(lambda _: self._sync(args))
                reactor.callLater(delay, df.callback, None)
                return df
            return res

        if self.retry:
            d.addCallback(_retry)
        return d

    def finish(self, res):
        d = defer.succeed(res)

        def _gotResults(results):
            self.setStatus(self.cmd, results)
            return results
        d.addCallback(_gotResults)
        d.addCallback(self.finished)
        return d

    def _getP4BaseForLog(self):
        return self.p4base or '<custom viewspec>'

    def _getP4BaseForCommand(self):
        return self.p4base or ''

    def _buildVCCommand(self, doCommand):
        assert doCommand, "No command specified"

        command = [self.p4bin, ]

        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if not self.use_tickets and self.p4passwd:
            # Need to find out if there's a way to obfuscate this
            command.extend(['-P', self.p4passwd])
        if self.p4client:
            command.extend(['-c', self.p4client])

        # Only add the extra arguments for the `sync` command.
        if doCommand[0] == 'sync' and self.p4extra_args:
            command.extend(self.p4extra_args)

        command.extend(doCommand)

        command = [c.encode('utf-8') for c in command]
        return command

    def _dovccmd(self, command, collectStdout=False, initialStdin=None, abandonOnFailure=True):
        command = self._buildVCCommand(command)

        if debug_logging:
            log.msg("P4:_dovccmd():workdir->%s" % self.workdir)

        cmd = buildstep.RemoteShellCommand(self.workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout,
                                           collectStdout=collectStdout,
                                           initialStdin=initialStdin,)
        cmd.useLog(self.stdio_log, False)
        if debug_logging:
            log.msg("Starting p4 command : p4 %s" % (" ".join(command),))

        d = self.runCommand(cmd)

        def evaluateCommand(cmd):
            if cmd.rc != 0 and abandonOnFailure:
                if debug_logging:
                    log.msg("P4:_dovccmd():Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            if collectStdout:
                return cmd.stdout
            else:
                return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    def _sourcedirIsUpdatable(self):
        # In general you should always be able to write to the directory
        # You just specified as the root of your client
        # So just return.
        # If we find a case where this is no longer true, then this
        # needs to be implemented
        return defer.succeed(True)

    @defer.inlineCallbacks
    def _createClientSpec(self):
        builddir = self.getProperty('builddir')

        if debug_logging:
            log.msg("P4:_createClientSpec() builddir:%s" % builddir)
            log.msg("P4:_createClientSpec() SELF.workdir:%s" % self.workdir)

        prop_dict = self.getProperties().asDict()
        prop_dict['p4client'] = self.p4client

        client_spec = ''
        client_spec += "Client: %s\n\n" % self.p4client
        client_spec += "Owner: %s\n\n" % self.p4user
        client_spec += "Description:\n\tCreated by %s\n\n" % self.p4user
        client_spec += "Root:\t%s\n\n" % self.build.path_module.normpath(
            self.build.path_module.join(builddir, self.workdir)
        )
        client_spec += "Options:\t%s\n\n" % self.p4client_spec_options
        if self.p4line_end:
            client_spec += "LineEnd:\t%s\n\n" % self.p4line_end
        else:
            client_spec += "LineEnd:\tlocal\n\n"

        # Setup a view
        client_spec += "View:\n"

        if self.p4viewspec:
            # uses only p4viewspec array of tuples to build view
            # If the user specifies a viewspec via an array of tuples then
            # Ignore any specified p4base,p4branch, and/or p4extra_views
            suffix = self.p4viewspec_suffix or ''
            for k, v in self.p4viewspec:
                if debug_logging:
                    log.msg('P4:_createClientSpec():key:%s value:%s' % (k, v))
                client_spec += '\t%s%s //%s/%s%s\n' % (k, suffix, self.p4client, v, suffix)
        else:
            # Uses p4base, p4branch, p4extra_views
            client_spec += "\t%s" % (self.p4base)

            if self.p4branch:
                client_spec += "/%s" % (self.p4branch)

            client_spec += "/... //%s/...\n" % (self.p4client)

            if self.p4extra_views:
                for k, v in self.p4extra_views:
                    client_spec += "\t%s/... //%s/%s/...\n" % (k, self.p4client, v)

        client_spec = client_spec.encode('utf-8')  # resolve unicode issues
        if debug_logging:
            log.msg(client_spec)

        stdout = yield self._dovccmd(['client', '-i'], collectStdout=True, initialStdin=client_spec)
        mo = re.search(r'Client (\S+) (.+)$', stdout, re.M)
        defer.returnValue(mo and (mo.group(2) == 'saved.' or mo.group(2) == 'not changed.'))

    @defer.inlineCallbacks
    def _acquireTicket(self, _):
        if debug_logging:
            log.msg("P4:acquireTicket()")

        # TODO: check first if the ticket is still valid?
        initialStdin = self.p4passwd + "\n"
        yield self._dovccmd(['login'], initialStdin=initialStdin)

    def parseGotRevision(self, _):
        command = self._buildVCCommand(['changes', '-m1', '#have'])

        cmd = buildstep.RemoteShellCommand(self.workdir, command,
                                           env=self.env,
                                           timeout=self.timeout,
                                           logEnviron=self.logEnviron,
                                           collectStdout=True)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        def _setrev(_):
            stdout = cmd.stdout.strip()
            # Example output from p4 changes -m1 #have
            #     Change 212798 on 2012/04/13 by user@user-unix-bldng2 'change to pickup build'
            revision = stdout.split()[1]
            try:
                int(revision)
            except ValueError:
                msg = ("p4.parseGotRevision unable to parse output "
                       "of 'p4 changes -m1 \"#have\"': '%s'" % stdout)
                log.msg(msg)
                raise buildstep.BuildStepFailed()

            if debug_logging:
                log.msg("Got p4 revision %s" % (revision,))
            self.updateSourceProperty('got_revision', revision)
            return 0
        d.addCallback(lambda _: _setrev(cmd.rc))
        return d

    def purge(self, ignore_ignores):
        """Delete everything that shown up on status."""
        command = ['sync', '#none']
        if ignore_ignores:
            command.append('--no-ignore')
        d = self._dovccmd(command, collectStdout=True)

        # add deferred to rm tree

        # then add defer to sync to revision
        return d

    def checkP4(self):
        cmd = buildstep.RemoteShellCommand(self.workdir, ['p4', '-V'],
                                           env=self.env,
                                           logEnviron=self.logEnviron)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)

        def evaluate(cmd):
            if cmd.rc != 0:
                return False
            return True
        d.addCallback(lambda _: evaluate(cmd))
        return d

    def computeSourceRevision(self, changes):
        if not changes or None in [c.revision for c in changes]:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange
