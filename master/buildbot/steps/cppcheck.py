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


import re

from twisted.internet import defer

from buildbot.process import logobserver
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import ShellMixin
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS


class Cppcheck(ShellMixin, BuildStep):
    # Highly inspired from the Pylint step.
    name = "cppcheck"
    description = ["running", "cppcheck"]
    descriptionDone = ["cppcheck"]
    flunkingIssues = ('error',)

    MESSAGES = (
        'error', 'warning', 'style', 'performance', 'portability', 'information')

    renderables = ('binary', 'source', 'extra_args')

    def __init__(self, *args, **kwargs):

        for name, default in [('binary', 'cppcheck'),
                              ('source', ['.']),
                              ('enable', []),
                              ('inconclusive', False),
                              ('extra_args', [])]:
            setattr(self, name, kwargs.pop(name, default))

        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super().__init__(*args, **kwargs)
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self._log_consumer))

        self.counts = {}
        summaries = self.summaries = {}
        for m in self.MESSAGES:
            self.counts[m] = 0
            summaries[m] = []

    def _log_consumer(self):
        line_re = re.compile(
                fr"(?:\[.+\]: )?\((?P<severity>{'|'.join(self.MESSAGES)})\) .+")

        while True:
            _, line = yield
            m = line_re.match(line)
            if m is not None:
                msgsev = m.group('severity')
                self.summaries[msgsev].append(line)
                self.counts[msgsev] += 1

    @defer.inlineCallbacks
    def run(self):
        command = [self.binary]
        command.extend(self.source)
        if self.enable:
            command.append(f"--enable={','.join(self.enable)}")
        if self.inconclusive:
            command.append('--inconclusive')
        command.extend(self.extra_args)

        cmd = yield self.makeRemoteShellCommand(command=command)

        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        self.descriptionDone = self.descriptionDone[:]
        for msg in self.MESSAGES:
            self.setProperty(f'cppcheck-{msg}', self.counts[msg], 'Cppcheck')
            if not self.counts[msg]:
                continue
            self.descriptionDone.append(f"{msg}={self.counts[msg]}")
            yield self.addCompleteLog(msg, '\n'.join(self.summaries[msg]))
        self.setProperty('cppcheck-total', sum(self.counts.values()), 'Cppcheck')

        yield self.updateSummary()

        if cmd.results() != SUCCESS:
            return cmd.results()

        for msg in self.flunkingIssues:
            if self.counts[msg] != 0:
                return FAILURE
        if sum(self.counts.values()) > 0:
            return WARNINGS
        return SUCCESS
