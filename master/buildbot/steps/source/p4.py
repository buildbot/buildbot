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

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot import interfaces
from buildbot.interfaces import WorkerSetupError
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.process import results
from buildbot.process.properties import Interpolate
from buildbot.steps.source import Source

# Notes:
#  see
# http://perforce.com/perforce/doc.current/manuals/cmdref/o.gopts.html#1040647
#   for getting p4 command to output marshalled python dictionaries as output
#   for commands.
#   Perhaps switch to using 'p4 -G' :  From URL above:
#   -G Causes all output (and batch input for form commands with -i) to be
#   formatted as marshalled Python dictionary objects. This is most often used
#   when scripting.


class P4(Source):

    """Perform Perforce checkout/update operations."""

    name = 'p4'

    renderables = ['mode', 'p4base', 'p4client', 'p4viewspec', 'p4branch', 'p4passwd']
    possible_modes = ('incremental', 'full')

    def __init__(self, mode='incremental',
                 method=None, p4base=None, p4branch=None,
                 p4port=None, p4user=None,
                 p4passwd=None, p4extra_views=(), p4line_end='local',
                 p4viewspec=None, p4viewspec_suffix='...',
                 p4client=Interpolate(
                     'buildbot_%(prop:workername)s_%(prop:buildername)s'),
                 p4client_spec_options='allwrite rmdir',
                 p4extra_args=None,
                 p4bin='p4',
                 use_tickets=False,
                 stream=False,
                 debug=False,
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
        self.stream = stream
        self.debug = debug

        super().__init__(**kwargs)

        if self.mode not in self.possible_modes and \
                not interfaces.IRenderable.providedBy(self.mode):
            config.error("mode {} is not an IRenderable, or one of {}".format(self.mode,
                                                                              self.possible_modes))

        if not p4viewspec and p4base is None:
            config.error("You must provide p4base or p4viewspec")

        if p4viewspec and (p4base or p4branch or p4extra_views):
            config.error(
                "Either provide p4viewspec or p4base and p4branch (and optionally p4extra_views)")

        if p4viewspec and isinstance(p4viewspec, str):
            config.error(
                "p4viewspec must not be a string, and should be a sequence of 2 element sequences")

        if not interfaces.IRenderable.providedBy(p4base) and p4base and not p4base.startswith('/'):
            config.error('p4base should start with // [p4base = {}]'.format(p4base))

        if not interfaces.IRenderable.providedBy(p4base) and p4base and p4base.endswith('/'):
            config.error('p4base should not end with a trailing / [p4base = {}]'.format(p4base))

        if not interfaces.IRenderable.providedBy(p4branch) and p4branch and p4branch.endswith('/'):
            config.error('p4branch should not end with a trailing / [p4branch = {}]'.format(
                    p4branch))

        if stream:
            if (p4extra_views or p4viewspec):
                config.error('You can\'t use p4extra_views not p4viewspec with stream')
            if not p4base or not p4branch:
                config.error('You must specify both p4base and p4branch when using stream')
            if not interfaces.IRenderable.providedBy(p4base) and " " in p4base:
                config.error('p4base must not contain any whitespace')
            if not interfaces.IRenderable.providedBy(p4branch) and " " in p4branch:
                config.error('p4branch must not contain any whitespace')

        if self.p4client_spec_options is None:
            self.p4client_spec_options = ''

    @defer.inlineCallbacks
    def run_vc(self, branch, revision, patch):
        if self.debug:
            log.msg('in run_vc')

        self.revision = revision
        self.method = self._getMethod()
        self.stdio_log = yield self.addLogForRemoteCommands("stdio")

        installed = yield self.checkP4()
        if not installed:
            raise WorkerSetupError("p4 is not installed on worker")

        # Try to obfuscate the password when used as an argument to commands.
        if self.p4passwd is not None:
            if not self.workerVersionIsOlderThan('shell', '2.16'):
                self.p4passwd_arg = ('obfuscated', self.p4passwd, 'XXXXXX')
            else:
                self.p4passwd_arg = self.p4passwd
                log.msg("Worker does not understand obfuscation; "
                        "p4 password will be logged")

        if self.use_tickets and self.p4passwd:
            yield self._acquireTicket()

        yield self._getAttrGroupMember('mode', self.mode)()
        yield self.parseGotRevision()
        return results.SUCCESS

    @defer.inlineCallbacks
    def mode_full(self):
        if self.debug:
            log.msg("P4:full()..")

        # First we need to create the client
        yield self._createClientSpec()

        # Then p4 sync #none
        yield self._dovccmd(['sync', '#none'])

        # Then remove directory.
        yield self.runRmdir(self.workdir)

        # Then we need to sync the client
        if self.revision:
            if self.debug:
                log.msg("P4: full() sync command based on :base:%s changeset:%d",
                        self._getP4BaseForLog(), int(self.revision))
            yield self._dovccmd(['sync', '{}...@{}'.format(self._getP4BaseForCommand(),
                                                           int(self.revision))], collectStdout=True)
        else:
            if self.debug:
                log.msg("P4: full() sync command based on :base:%s no revision",
                        self._getP4BaseForLog())
            yield self._dovccmd(['sync'], collectStdout=True)

        if self.debug:
            log.msg("P4: full() sync done.")

    @defer.inlineCallbacks
    def mode_incremental(self):
        if self.debug:
            log.msg("P4:incremental()")

        # First we need to create the client
        yield self._createClientSpec()

        # and plan to do a checkout
        command = ['sync', ]

        if self.revision:
            command.extend(['{}...@{}'.format(self._getP4BaseForCommand(), int(self.revision))])

        if self.debug:
            log.msg(
                "P4:incremental() command:%s revision:%s", command, self.revision)
        yield self._dovccmd(command)

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
            command.extend(['-P', self.p4passwd_arg])
        if self.p4client:
            command.extend(['-c', self.p4client])

        # Only add the extra arguments for the `sync` command.
        if doCommand[0] == 'sync' and self.p4extra_args:
            command.extend(self.p4extra_args)

        command.extend(doCommand)
        return command

    @defer.inlineCallbacks
    def _dovccmd(self, command, collectStdout=False, initialStdin=None):
        command = self._buildVCCommand(command)

        if self.debug:
            log.msg("P4:_dovccmd():workdir->{}".format(self.workdir))

        cmd = remotecommand.RemoteShellCommand(self.workdir, command,
                                               env=self.env,
                                               logEnviron=self.logEnviron,
                                               timeout=self.timeout,
                                               collectStdout=collectStdout,
                                               initialStdin=initialStdin,)
        cmd.useLog(self.stdio_log, False)
        if self.debug:
            log.msg("Starting p4 command : p4 {}".format(" ".join(command)))

        yield self.runCommand(cmd)

        if cmd.rc != 0:
            if self.debug:
                log.msg("P4:_dovccmd():Source step failed while running command {}".format(cmd))
            raise buildstep.BuildStepFailed()
        if collectStdout:
            return cmd.stdout
        return cmd.rc

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'
        return None

    @defer.inlineCallbacks
    def _createClientSpec(self):
        builddir = self.getProperty('builddir')

        if self.debug:
            log.msg("P4:_createClientSpec() builddir:{}".format(builddir))
            log.msg("P4:_createClientSpec() SELF.workdir:{}".format(self.workdir))

        prop_dict = self.getProperties().asDict()
        prop_dict['p4client'] = self.p4client

        client_spec = ''
        client_spec += "Client: {}\n\n".format(self.p4client)
        client_spec += "Owner: {}\n\n".format(self.p4user)
        client_spec += "Description:\n\tCreated by {}\n\n".format(self.p4user)
        client_spec += "Root:\t{}\n\n".format(self.build.path_module.normpath(
            self.build.path_module.join(builddir, self.workdir)))
        client_spec += "Options:\t{}\n\n".format(self.p4client_spec_options)
        if self.p4line_end:
            client_spec += "LineEnd:\t{}\n\n".format(self.p4line_end)
        else:
            client_spec += "LineEnd:\tlocal\n\n"

        # Perforce generates the view for stream-associated workspaces
        if self.stream:
            client_spec += "Stream:\t{}/{}\n".format(self.p4base, self.p4branch)
        else:
            # Setup a view
            client_spec += "View:\n"

            def has_whitespace(*args):
                return any([re.search(r'\s', i) for i in args if i is not None])

            if self.p4viewspec:
                # uses only p4viewspec array of tuples to build view
                # If the user specifies a viewspec via an array of tuples then
                # Ignore any specified p4base,p4branch, and/or p4extra_views
                suffix = self.p4viewspec_suffix or ''
                for k, v in self.p4viewspec:
                    if self.debug:
                        log.msg('P4:_createClientSpec():key:{} value:{}'.format(k, v))

                    qa = '"' if has_whitespace(k, suffix) else ''
                    qb = '"' if has_whitespace(self.p4client, v, suffix) else ''
                    client_spec += '\t{}{}{}{} {}//{}/{}{}{}\n'.format(qa, k, suffix, qa, qb,
                                                                       self.p4client, v, suffix, qb)
            else:
                # Uses p4base, p4branch, p4extra_views

                qa = '"' if has_whitespace(self.p4base, self.p4branch) else ''

                client_spec += "\t{}{}".format(qa, self.p4base)

                if self.p4branch:
                    client_spec += "/{}".format(self.p4branch)

                client_spec += "/...{} ".format(qa)

                qb = '"' if has_whitespace(self.p4client) else ''
                client_spec += "{}//{}/...{}\n".format(qb, self.p4client, qb)

                if self.p4extra_views:
                    for k, v in self.p4extra_views:
                        qa = '"' if has_whitespace(k) else ''
                        qb = '"' if has_whitespace(k, self.p4client, v) else ''

                        client_spec += "\t{}{}/...{} {}//{}/{}/...{}\n".format(qa, k, qa, qb,
                                                                               self.p4client, v, qb)

        if self.debug:
            log.msg(client_spec)

        stdout = yield self._dovccmd(['client', '-i'], collectStdout=True, initialStdin=client_spec)
        mo = re.search(r'Client (\S+) (.+)$', stdout, re.M)
        return mo and (mo.group(2) == 'saved.' or mo.group(2) == 'not changed.')

    @defer.inlineCallbacks
    def _acquireTicket(self):
        if self.debug:
            log.msg("P4:acquireTicket()")

        # TODO: check first if the ticket is still valid?
        initialStdin = self.p4passwd + "\n"
        yield self._dovccmd(['login'], initialStdin=initialStdin)

    @defer.inlineCallbacks
    def parseGotRevision(self):
        command = self._buildVCCommand(['changes', '-m1', '#have'])

        cmd = remotecommand.RemoteShellCommand(self.workdir, command,
                                               env=self.env,
                                               timeout=self.timeout,
                                               logEnviron=self.logEnviron,
                                               collectStdout=True)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)

        stdout = cmd.stdout.strip()
        # Example output from p4 changes -m1 #have
        # Change 212798 on 2012/04/13 by user@user-unix-bldng2 'change to
        # pickup build'
        revision = stdout.split()[1]
        try:
            int(revision)
        except ValueError as e:
            msg = (("p4.parseGotRevision unable to parse output "
                    "of 'p4 changes -m1 \"#have\"': '{}'").format(stdout))
            log.msg(msg)
            raise buildstep.BuildStepFailed() from e

        if self.debug:
            log.msg("Got p4 revision {}".format(revision))
        self.updateSourceProperty('got_revision', revision)

    @defer.inlineCallbacks
    def purge(self, ignore_ignores):
        """Delete everything that shown up on status."""
        command = ['sync', '#none']
        if ignore_ignores:
            command.append('--no-ignore')
        yield self._dovccmd(command, collectStdout=True)
        # FIXME: do the following comments need addressing?
        # add deferred to rm tree
        # then add defer to sync to revision

    @defer.inlineCallbacks
    def checkP4(self):
        cmd = remotecommand.RemoteShellCommand(self.workdir, [self.p4bin, '-V'],
                                               env=self.env,
                                               logEnviron=self.logEnviron)
        cmd.useLog(self.stdio_log, False)
        yield self.runCommand(cmd)
        return cmd.rc == 0

    def computeSourceRevision(self, changes):
        if not changes or None in [c.revision for c in changes]:
            return None
        lastChange = max([int(c.revision) for c in changes])
        return lastChange
