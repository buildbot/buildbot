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

from buildbot.process import logobserver
from buildbot.status.results import FAILURE
from buildbot.status.results import WARNINGS
from buildbot.status.results import SUCCESS
from buildbot.steps.shell import ShellCommand


class Cppcheck(ShellCommand):
    # Highly inspirated from the Pylint step.
    name = "cppcheck"
    command = ["cppcheck"]
    description = ["running", "cppcheck"]
    descriptionDone = ["cppcheck"]
    flunkingIssues = ('error',)

    MESSAGES = (
        'error', 'warning', 'style', 'performance', 'portability', 'information')

    def __init__(self, *args, **kwargs):
        self.source = ['.']
        if 'source' in kwargs:
            self.source = kwargs['source']
            del kwargs['source']
        self.extra_args = ['--enable=all', '--inconclusive']
        if 'extra_args' in kwargs:
            self.extra_args = kwargs['extra_args']
            del kwargs['extra_args']
        ShellCommand.__init__(self, *args, **kwargs)
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

        self.command = self.command[:]
        self.command.extend(self.source)
        self.command.extend(self.extra_args)

        counts = self.counts = {}
        summaries = self.summaries = {}
        for m in self.MESSAGES:
            counts[m] = 0
            summaries[m] = []

    def logConsumer(self):
        line_re = re.compile(
            '(?:\[.+\]: )?\((?P<severity>%s)\) .+' % '|'.join(self.MESSAGES))

        while True:
            stream, line = yield
            m = line_re.match(line)
            if m is not None:
                msgsev = m.group('severity')
                self.summaries[msgsev].append(line)
                self.counts[msgsev] += 1

    def createSummary(self, log):
        self.descriptionDone = self.descriptionDone[:]
        for msg in self.MESSAGES:
            self.setProperty('cppcheck-%s' % msg, self.counts[msg])
            if not self.counts[msg]:
                continue
            self.descriptionDone.append("%s=%d" % (msg, self.counts[msg]))
            self.addCompleteLog(msg, '\n'.join(self.summaries[msg]))
        self.setProperty('cppcheck-total', sum(self.counts.values()))

    def evaluateCommand(self, cmd):
        """ cppcheck always return 0, unless a special parameter is given """
        for msg in self.flunkingIssues:
            if self.counts[msg] != 0:
                return FAILURE
        if self.getProperty('cppcheck-total') != 0:
            return WARNINGS
        return SUCCESS
