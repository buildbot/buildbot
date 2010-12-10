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

import os, re

from twisted.python import log

from buildslave.commands.base import SourceBaseCommand
from buildslave import runprocess
from buildslave.util import Obfuscated


class P4Base(SourceBaseCommand):
    """Base class for P4 source-updaters

    ['p4port'] (required): host:port for server to access
    ['p4user'] (optional): user to use for access
    ['p4passwd'] (optional): passwd to try for the user
    ['p4client'] (optional): client spec to use
    """
    def setup(self, args):
        SourceBaseCommand.setup(self, args)
        self.p4port = args['p4port']
        self.p4client = args['p4client']
        self.p4user = args['p4user']
        self.p4passwd = args['p4passwd']

    def parseGotRevision(self):
        # Executes a p4 command that will give us the latest changelist number
        # of any file under the current (or default) client:
        command = ['p4']
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
        if self.p4client:
            command.extend(['-c', self.p4client])
        # add '-s submitted' for bug #626
        command.extend(['changes', '-s', 'submitted', '-m', '1', '#have'])
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         environ=self.env, timeout=self.timeout,
                         maxTime=self.maxTime, sendStdout=True,
                         sendRC=False, keepStdout=True,
                         usePTY=False)
        self.command = c
        d = c.start()

        def _parse(res):
            # 'p4 -c clien-name change -m 1 "#have"' will produce an output like:
            # "Change 28147 on 2008/04/07 by p4user@hostname..."
            # The number after "Change" is the one we want.
            m = re.match('Change\s+(\d+)\s+', c.stdout)
            if m:
                return m.group(1)
            return None
        d.addCallback(_parse)
        return d


class P4(P4Base):
    """A P4 source-updater.

    ['p4port'] (required): host:port for server to access
    ['p4user'] (required): user to use for access
    ['p4passwd'] (required): passwd to try for the user
    ['p4client'] (required): client spec to use
    ['p4extra_views'] (required): additional client views to use
    ['p4base'] (required): view into the Perforce depot without branch name or trailing "..."
    ['p4line_end'] (optional): value of the LineEnd client specification property
    """

    header = "p4"

    def setup(self, args):
        P4Base.setup(self, args)
        self.p4base = args['p4base']
        self.p4extra_views = args['p4extra_views']
        self.p4line_end = args.get('p4line_end', None)
        self.p4mode = args['mode']
        self.p4branch = args['branch']

        self.sourcedata = str([
            # Perforce server.
            self.p4port,

            # Client spec.
            self.p4client,

            # Depot side of view spec.
            self.p4base,
            self.p4branch,
            self.p4extra_views,
            self.p4line_end,

            # Local side of view spec (srcdir is made from these).
            self.builder.basedir,
            self.mode,
            self.workdir
        ])


    def sourcedirIsUpdateable(self):
        # We assume our client spec is still around.
        # We just say we aren't updateable if the dir doesn't exist so we
        # don't get ENOENT checking the sourcedata.
        return (not self.sourcedirIsPatched() and
                os.path.isdir(os.path.join(self.builder.basedir,
                                           self.srcdir)))

    def doVCUpdate(self):
        return self._doP4Sync(force=False)

    def _doP4Sync(self, force):
        command = ['p4']

        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
        if self.p4client:
            command.extend(['-c', self.p4client])
        command.extend(['sync'])
        if force:
            command.extend(['-f'])
        if self.revision:
            command.extend(['@' + str(self.revision)])
        env = {}
        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         environ=env, sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        return d


    def doVCFull(self):
        env = {}
        command = ['p4']
        client_spec = ''
        client_spec += "Client: %s\n\n" % self.p4client
        client_spec += "Owner: %s\n\n" % self.p4user
        client_spec += "Description:\n\tCreated by %s\n\n" % self.p4user
        client_spec += "Root:\t%s\n\n" % self.builder.basedir
        client_spec += "Options:\tallwrite rmdir\n\n"
        if self.p4line_end:
            client_spec += "LineEnd:\t%s\n\n" % self.p4line_end
        else:
            client_spec += "LineEnd:\tlocal\n\n"

        # Setup a view
        client_spec += "View:\n\t%s" % (self.p4base)
        if self.p4branch:
            client_spec += "%s/" % (self.p4branch)
        client_spec += "... //%s/%s/...\n" % (self.p4client, self.srcdir)
        if self.p4extra_views:
            for k, v in self.p4extra_views:
                client_spec += "\t%s/... //%s/%s%s/...\n" % (k, self.p4client,
                                                             self.srcdir, v)
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
        command.extend(['client', '-i'])
        log.msg(client_spec)

        # from bdbaddog in github comments:
        # I'm pretty sure the issue is that perforce client specs can't be
        # non-ascii (unless you configure at initial config to be unicode). I
        # floated a question to perforce mailing list.  From reading the
        # internationalization notes..
        #   http://www.perforce.com/perforce/doc.092/user/i18nnotes.txt
        # I'm 90% sure that's the case.
        # (http://github.com/bdbaddog/buildbot/commit/8420149b2b804efcf5f81a13e18aa62da0424d21)

        # Clean client spec to plain ascii
        client_spec=client_spec.encode('ascii','ignore')

        c = runprocess.RunProcess(self.builder, command, self.builder.basedir,
                         environ=env, sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, initialStdin=client_spec,
                         usePTY=False)
        self.command = c
        d = c.start()
        d.addCallback(self._abandonOnFailure)
        d.addCallback(lambda _: self._doP4Sync(force=True))
        return d

    def parseGotRevision(self):
        if self.revision:
            return str(self.revision)
        else:
            return P4Base.parseGotRevision(self)


class P4Sync(P4Base):
    """A partial P4 source-updater. Requires manual setup of a per-slave P4
    environment. The only thing which comes from the master is P4PORT.
    'mode' is required to be 'copy'.

    ['p4port'] (required): host:port for server to access
    ['p4user'] (optional): user to use for access
    ['p4passwd'] (optional): passwd to try for the user
    ['p4client'] (optional): client spec to use
    """

    header = "p4 sync"

    def setup(self, args):
        P4Base.setup(self, args)

    def sourcedirIsUpdateable(self):
        return True

    def _doVC(self, force):
        d = os.path.join(self.builder.basedir, self.srcdir)
        command = [self.getCommand('p4')]
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        if self.p4passwd:
            command.extend(['-P', Obfuscated(self.p4passwd, "XXXXXXXX")])
        if self.p4client:
            command.extend(['-c', self.p4client])
        command.extend(['sync'])
        if force:
            command.extend(['-f'])
        if self.revision:
            command.extend(['@' + self.revision])
        env = {}
        c = runprocess.RunProcess(self.builder, command, d, environ=env,
                         sendRC=False, timeout=self.timeout,
                         maxTime=self.maxTime, usePTY=False)
        self.command = c
        return c.start()

    def doVCUpdate(self):
        return self._doVC(force=False)

    def doVCFull(self):
        return self._doVC(force=True)

    def parseGotRevision(self):
        if self.revision:
            return str(self.revision)
        else:
            return P4Base.parseGotRevision(self)
