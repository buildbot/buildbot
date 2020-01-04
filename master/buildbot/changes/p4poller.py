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
# Portions Copyright Buildbot Team Members
# Portions Copyright 2011 National Instruments


# Many thanks to Dave Peticolas for contributing this module

import datetime
import os
import re

import dateutil.tz

from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import utils
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.changes import base
from buildbot.util import bytes2unicode

debug_logging = False


class P4PollerError(Exception):

    """Something went wrong with the poll. This is used as a distinctive
    exception type so that unit tests can detect and ignore it."""


class TicketLoginProtocol(protocol.ProcessProtocol):

    """ Twisted process protocol to run `p4 login` and enter our password
        in the stdin."""

    def __init__(self, stdin, p4base):
        self.deferred = defer.Deferred()
        self.stdin = stdin.encode('ascii')
        self.stdout = b''
        self.stderr = b''
        self.p4base = p4base

    def connectionMade(self):
        if self.stdin:
            if debug_logging:
                log.msg("P4Poller: entering password for %s: %s" %
                        (self.p4base, self.stdin))
            self.transport.write(self.stdin)
        self.transport.closeStdin()

    def processEnded(self, reason):
        if debug_logging:
            log.msg("P4Poller: login process finished for %s: %s" %
                    (self.p4base, reason.value.exitCode))
        self.deferred.callback(reason.value.exitCode)

    def outReceived(self, data):
        if debug_logging:
            log.msg("P4Poller: login stdout for %s: %s" % (self.p4base, data))
        self.stdout += data

    def errReceived(self, data):
        if debug_logging:
            log.msg("P4Poller: login stderr for %s: %s" % (self.p4base, data))
        self.stderr += data


def get_simple_split(branchfile):
    """Splits the branchfile argument and assuming branch is
       the first path component in branchfile, will return
       branch and file else None."""

    index = branchfile.find('/')
    if index == -1:
        return None, None
    branch, file = branchfile.split('/', 1)
    return branch, file


class P4Source(base.PollingChangeSource, util.ComparableMixin):

    """This source will poll a perforce repository for changes and submit
    them to the change master."""

    compare_attrs = ("p4port", "p4user", "p4passwd", "p4base",
                     "p4bin", "pollInterval", "pollAtLaunch",
                     "server_tz")

    env_vars = ["P4CLIENT", "P4PORT", "P4PASSWD", "P4USER",
                "P4CHARSET", "PATH", "P4CONFIG"]

    changes_line_re = re.compile(
        r"Change (?P<num>\d+) on \S+ by \S+@\S+ '.*'$")
    describe_header_re = re.compile(
        r"Change \d+ by (?P<who>\S+)@\S+ on (?P<when>.+)$")
    file_re = re.compile(r"^\.\.\. (?P<path>[^#]+)#\d+ [/\w]+$")
    datefmt = '%Y/%m/%d %H:%M:%S'

    parent = None  # filled in when we're added
    last_change = None
    loop = None

    def __init__(self, p4port=None, p4user=None, p4passwd=None,
                 p4base='//', p4bin='p4',
                 split_file=lambda branchfile: (None, branchfile),
                 pollInterval=60 * 10, histmax=None, pollinterval=-2,
                 encoding='utf8', project=None, name=None,
                 use_tickets=False, ticket_login_interval=60 * 60 * 24,
                 server_tz=None, pollAtLaunch=False, revlink=lambda branch, revision: (''), resolvewho=lambda who: (who)):

        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval

        if name is None:
            name = "P4Source:%s:%s" % (p4port, p4base)

        super().__init__(name=name,
                         pollInterval=pollInterval,
                         pollAtLaunch=pollAtLaunch)

        if project is None:
            project = ''

        if use_tickets and not p4passwd:
            config.error(
                "You need to provide a P4 password to use ticket authentication")

        if not callable(revlink):
            config.error(
                "You need to provide a valid callable for revlink")

        if not callable(resolvewho):
            config.error(
                "You need to provide a valid callable for resolvewho")

        self.p4port = p4port
        self.p4user = p4user
        self.p4passwd = p4passwd
        self.p4base = p4base
        self.p4bin = p4bin
        self.split_file = split_file
        self.encoding = encoding
        self.project = util.bytes2unicode(project)
        self.use_tickets = use_tickets
        self.ticket_login_interval = ticket_login_interval
        self.revlink_callable = revlink
        self.resolvewho_callable = resolvewho
        self.server_tz = dateutil.tz.gettz(server_tz) if server_tz else None
        if server_tz is not None and self.server_tz is None:
            raise P4PollerError("Failed to get timezone from server_tz string '{}'".format(server_tz))

        self._ticket_passwd = None
        self._ticket_login_counter = 0

    def describe(self):
        return "p4source %s %s" % (self.p4port, self.p4base)

    def poll(self):
        d = self._poll()
        d.addErrback(log.err, 'P4 poll failed on %s, %s' %
                     (self.p4port, self.p4base))
        return d

    def _get_process_output(self, args):
        env = {e: os.environ.get(e)
               for e in self.env_vars if os.environ.get(e)}
        d = utils.getProcessOutput(self.p4bin, args, env)
        return d

    def _acquireTicket(self, protocol):
        command = [self.p4bin, ]
        if self.p4port:
            command.extend(['-p', self.p4port])
        if self.p4user:
            command.extend(['-u', self.p4user])
        command.extend(['login', '-p'])
        command = [c.encode('utf-8') for c in command]

        reactor.spawnProcess(protocol, self.p4bin, command, env=os.environ)

    def _parseTicketPassword(self, stdout):
        try:
            stdout = stdout.decode(self.encoding, errors='strict')
        except Exception as e:
            raise P4PollerError('Failed to parse P4 ticket: {}'.format(e))

        lines = stdout.splitlines()
        if len(lines) < 2:
            return None
        return lines[-1].strip()

    def _getPasswd(self):
        if self.use_tickets:
            return self._ticket_passwd
        return self.p4passwd

    @defer.inlineCallbacks
    def _poll(self):
        if self.use_tickets:
            self._ticket_login_counter -= 1
            if self._ticket_login_counter <= 0:
                # Re-acquire the ticket and reset the counter.
                log.msg("P4Poller: (re)acquiring P4 ticket for %s..." %
                        self.p4base)
                protocol = TicketLoginProtocol(
                    self.p4passwd + "\n", self.p4base)
                self._acquireTicket(protocol)
                yield protocol.deferred

                self._ticket_passwd = self._parseTicketPassword(
                    protocol.stdout)
                self._ticket_login_counter = max(
                    self.ticket_login_interval / self.pollInterval, 1)
                if debug_logging:
                    log.msg("P4Poller: got ticket password: %s" %
                            self._ticket_passwd)
                    log.msg(
                        "P4Poller: next ticket acquisition in %d polls" % self._ticket_login_counter)

        args = []
        if self.p4port:
            args.extend(['-p', self.p4port])
        if self.p4user:
            args.extend(['-u', self.p4user])
        if self.p4passwd:
            args.extend(['-P', self._getPasswd()])
        args.extend(['changes'])
        if self.last_change is not None:
            args.extend(
                ['%s...@%d,#head' % (self.p4base, self.last_change + 1)])
        else:
            args.extend(['-m', '1', '%s...' % (self.p4base,)])

        result = yield self._get_process_output(args)
        # decode the result from its designated encoding
        try:
            result = bytes2unicode(result, self.encoding)
        except UnicodeError as ex:
            log.msg("{}: cannot fully decode {} in {}".format(
                    ex, repr(result), self.encoding))
            result = bytes2unicode(result, encoding=self.encoding, errors="replace")

        last_change = self.last_change
        changelists = []
        for line in result.split('\n'):
            line = line.strip()
            if not line:
                continue
            m = self.changes_line_re.match(line)
            if not m:
                raise P4PollerError(
                    "Unexpected 'p4 changes' output: %r" % result)
            num = int(m.group('num'))
            if last_change is None:
                # first time through, the poller just gets a "baseline" for where to
                # start on the next poll
                log.msg('P4Poller: starting at change %d' % num)
                self.last_change = num
                return
            changelists.append(num)
        changelists.reverse()  # oldest first

        # Retrieve each sequentially.
        for num in changelists:
            args = []
            if self.p4port:
                args.extend(['-p', self.p4port])
            if self.p4user:
                args.extend(['-u', self.p4user])
            if self.p4passwd:
                args.extend(['-P', self._getPasswd()])
            args.extend(['describe', '-s', str(num)])
            result = yield self._get_process_output(args)

            # decode the result from its designated encoding
            try:
                result = bytes2unicode(result, self.encoding)
            except UnicodeError as ex:
                log.msg(
                    "P4Poller: couldn't decode changelist description: %s" % ex.encoding)
                log.msg("P4Poller: in object: %s" % ex.object)
                log.err("P4Poller: poll failed on %s, %s" %
                        (self.p4port, self.p4base))
                raise

            lines = result.split('\n')
            # SF#1555985: Wade Brainerd reports a stray ^M at the end of the date
            # field. The rstrip() is intended to remove that.
            lines[0] = lines[0].rstrip()
            m = self.describe_header_re.match(lines[0])
            if not m:
                raise P4PollerError(
                    "Unexpected 'p4 describe -s' result: %r" % result)
            who = self.resolvewho_callable(m.group('who'))
            when = datetime.datetime.strptime(m.group('when'), self.datefmt)
            if self.server_tz:
                # Convert from the server's timezone to the local timezone.
                when = when.replace(tzinfo=self.server_tz)
            when = util.datetime2epoch(when)

            comment_lines = []
            lines.pop(0)  # describe header
            lines.pop(0)  # blank line
            while not lines[0].startswith('Affected files'):
                if lines[0].startswith('\t'):  # comment is indented by one tab
                    comment_lines.append(lines.pop(0)[1:])
                else:
                    lines.pop(0)  # discard non comment line
            comments = '\n'.join(comment_lines)

            lines.pop(0)  # affected files
            branch_files = {}  # dict for branch mapped to file(s)
            while lines:
                line = lines.pop(0).strip()
                if not line:
                    continue
                m = self.file_re.match(line)
                if not m:
                    raise P4PollerError("Invalid file line: %r" % line)
                path = m.group('path')
                if path.startswith(self.p4base):
                    branch, file = self.split_file(path[len(self.p4base):])
                    if (branch is None and file is None):
                        continue
                    if branch in branch_files:
                        branch_files[branch].append(file)
                    else:
                        branch_files[branch] = [file]

            for branch in branch_files:
                yield self.master.data.updates.addChange(
                    author=who,
                    committer=None,
                    files=branch_files[branch],
                    comments=comments,
                    revision=str(num),
                    when_timestamp=when,
                    branch=branch,
                    project=self.project,
                    revlink=self.revlink_callable(branch, str(num)))

            self.last_change = num
