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
from future.utils import iteritems

import re

from buildbot import config
from buildbot.process import logobserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps.shell import ShellCommand


class BuildEPYDoc(ShellCommand):
    name = "epydoc"
    command = ["make", "epydocs"]
    description = ["building", "epydocs"]
    descriptionDone = ["epydoc"]

    def __init__(self, **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    def logConsumer(self):
        self.import_errors = 0
        self.warnings = 0
        self.errors = 0

        while True:
            stream, line = yield
            if line.startswith("Error importing "):
                self.import_errors += 1
            if line.find("Warning: ") != -1:
                self.warnings += 1
            if line.find("Error: ") != -1:
                self.errors += 1

    def createSummary(self, log):
        self.descriptionDone = self.descriptionDone[:]
        if self.import_errors:
            self.descriptionDone.append("ierr=%d" % self.import_errors)
        if self.warnings:
            self.descriptionDone.append("warn=%d" % self.warnings)
        if self.errors:
            self.descriptionDone.append("err=%d" % self.errors)

    def evaluateCommand(self, cmd):
        if cmd.didFail():
            return FAILURE
        if self.warnings or self.errors:
            return WARNINGS
        return SUCCESS


class PyFlakes(ShellCommand):
    name = "pyflakes"
    command = ["make", "pyflakes"]
    description = ["running", "pyflakes"]
    descriptionDone = ["pyflakes"]
    flunkOnFailure = False

    # any pyflakes lines like this cause FAILURE
    _flunkingIssues = ("undefined",)

    _MESSAGES = ("unused", "undefined", "redefs", "import*", "misc")

    def __init__(self, *args, **kwargs):
        # PyFlakes return 1 for both warnings and errors. We
        # categorize this initially as WARNINGS so that
        # evaluateCommand below can inspect the results more closely.
        kwargs['decodeRC'] = {0: SUCCESS, 1: WARNINGS}
        ShellCommand.__init__(self, *args, **kwargs)
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

        counts = self.counts = {}
        summaries = self.summaries = {}
        for m in self._MESSAGES:
            counts[m] = 0
            summaries[m] = []

        # we need a separate variable for syntax errors
        self._hasSyntaxError = False

    def logConsumer(self):
        counts = self.counts
        summaries = self.summaries
        first = True
        while True:
            stream, line = yield
            if stream == 'h':
                continue
            # the first few lines might contain echoed commands from a 'make
            # pyflakes' step, so don't count these as warnings. Stop ignoring
            # the initial lines as soon as we see one with a colon.
            if first:
                if ':' in line:
                    # there's the colon, this is the first real line
                    first = False
                    # fall through and parse the line
                else:
                    # skip this line, keep skipping non-colon lines
                    continue

            if line.find("imported but unused") != -1:
                m = "unused"
            elif line.find("*' used; unable to detect undefined names") != -1:
                m = "import*"
            elif line.find("undefined name") != -1:
                m = "undefined"
            elif line.find("redefinition of unused") != -1:
                m = "redefs"
            elif line.find("invalid syntax") != -1:
                self._hasSyntaxError = True
                # we can do this, because if a syntax error occurs
                # the output will only contain the info about it, nothing else
                m = "misc"
            else:
                m = "misc"

            summaries[m].append(line)
            counts[m] += 1

    def createSummary(self, log):
        counts, summaries = self.counts, self.summaries
        self.descriptionDone = self.descriptionDone[:]

        # we log 'misc' as syntax-error
        if self._hasSyntaxError:
            self.addCompleteLog("syntax-error", "\n".join(summaries['misc']))
        else:
            for m in self._MESSAGES:
                if counts[m]:
                    self.descriptionDone.append("%s=%d" % (m, counts[m]))
                    self.addCompleteLog(m, "\n".join(summaries[m]))
                self.setProperty("pyflakes-%s" % m, counts[m], "pyflakes")
            self.setProperty("pyflakes-total", sum(counts.values()),
                             "pyflakes")

    def evaluateCommand(self, cmd):
        if cmd.didFail() or self._hasSyntaxError:
            return FAILURE
        for m in self._flunkingIssues:
            if self.getProperty("pyflakes-%s" % m):
                return FAILURE
        if self.getProperty("pyflakes-total"):
            return WARNINGS
        return SUCCESS


class PyLint(ShellCommand):

    '''A command that knows about pylint output.
    It is a good idea to add --output-format=parseable to your
    command, since it includes the filename in the message.
    '''
    name = "pylint"
    description = ["running", "pylint"]
    descriptionDone = ["pylint"]

    # pylint's return codes (see pylint(1) for details)
    # 1 - 16 will be bit-ORed

    RC_OK = 0
    RC_FATAL = 1
    RC_ERROR = 2
    RC_WARNING = 4
    RC_REFACTOR = 8
    RC_CONVENTION = 16
    RC_USAGE = 32

    # Using the default text output, the message format is :
    # MESSAGE_TYPE: LINE_NUM:[OBJECT:] MESSAGE
    # with --output-format=parseable it is: (the outer brackets are literal)
    # FILE_NAME:LINE_NUM: [MESSAGE_TYPE[, OBJECT]] MESSAGE
    # message type consists of the type char and 4 digits
    # The message types:

    _MESSAGES = {
        'C': "convention",  # for programming standard violation
        'R': "refactor",  # for bad code smell
        'W': "warning",  # for python specific problems
        'E': "error",  # for much probably bugs in the code
        'F': "fatal",  # error prevented pylint from further processing.
        'I': "info",
    }

    _flunkingIssues = ("F", "E")  # msg categories that cause FAILURE

    _re_groupname = 'errtype'
    _msgtypes_re_str = '(?P<%s>[%s])' % (
        _re_groupname, ''.join(list(_MESSAGES)))
    _default_line_re = re.compile(
        r'^%s(\d{4})?: *\d+(, *\d+)?:.+' % _msgtypes_re_str)
    _parseable_line_re = re.compile(
        r'[^:]+:\d+: \[%s(\d{4})?(\([a-z-]+\))?[,\]] .+' % _msgtypes_re_str)

    def __init__(self, **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.counts = {}
        self.summaries = {}
        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    def logConsumer(self):
        for m in self._MESSAGES:
            self.counts[m] = 0
            self.summaries[m] = []

        line_re = None  # decide after first match
        while True:
            stream, line = yield
            if stream == 'h':
                continue
            if not line_re:
                # need to test both and then decide on one
                if self._parseable_line_re.match(line):
                    line_re = self._parseable_line_re
                elif self._default_line_re.match(line):
                    line_re = self._default_line_re
                else:  # no match yet
                    continue
            mo = line_re.match(line)
            if mo:
                msgtype = mo.group(self._re_groupname)
                assert msgtype in self._MESSAGES
                self.summaries[msgtype].append(line)
                self.counts[msgtype] += 1

    def createSummary(self, log):
        counts, summaries = self.counts, self.summaries
        self.descriptionDone = self.descriptionDone[:]
        for msg, fullmsg in sorted(iteritems(self._MESSAGES)):
            if counts[msg]:
                self.descriptionDone.append("%s=%d" % (fullmsg, counts[msg]))
                self.addCompleteLog(fullmsg, "\n".join(summaries[msg]))
            self.setProperty("pylint-%s" % fullmsg, counts[msg], 'Pylint')
        self.setProperty("pylint-total", sum(counts.values()), 'Pylint')

    def evaluateCommand(self, cmd):
        if cmd.rc & (self.RC_FATAL | self.RC_ERROR | self.RC_USAGE):
            return FAILURE
        for msg in self._flunkingIssues:
            if self.getProperty("pylint-%s" % self._MESSAGES[msg]):
                return FAILURE
        if self.getProperty("pylint-total"):
            return WARNINGS
        return SUCCESS


class Sphinx(ShellCommand):

    ''' A Step to build sphinx documentation '''

    name = "sphinx"
    description = ["running", "sphinx"]
    descriptionDone = ["sphinx"]

    haltOnFailure = True

    def __init__(self, sphinx_sourcedir='.', sphinx_builddir=None,
                 sphinx_builder=None, sphinx='sphinx-build', tags=None,
                 defines=None, mode='incremental', **kwargs):

        if tags is None:
            tags = []

        if defines is None:
            defines = {}

        if sphinx_builddir is None:
            # Who the heck is not interested in the built doc ?
            config.error("Sphinx argument sphinx_builddir is required")

        if mode not in ('incremental', 'full'):
            config.error("Sphinx argument mode has to be 'incremental' or" +
                         "'full' is required")

        self.success = False
        ShellCommand.__init__(self, **kwargs)

        # build the command
        command = [sphinx]
        if sphinx_builder is not None:
            command.extend(['-b', sphinx_builder])

        for tag in tags:
            command.extend(['-t', tag])

        for key in sorted(defines):
            if defines[key] is None:
                command.extend(['-D', key])
            elif isinstance(defines[key], bool):
                command.extend(['-D',
                                '%s=%d' % (key, defines[key] and 1 or 0)])
            else:
                command.extend(['-D', '%s=%s' % (key, defines[key])])

        if mode == 'full':
            command.extend(['-E'])  # Don't use a saved environment

        command.extend([sphinx_sourcedir, sphinx_builddir])
        self.setCommand(command)

        self.addLogObserver(
            'stdio', logobserver.LineConsumerLogObserver(self.logConsumer))

    _msgs = ('WARNING', 'ERROR', 'SEVERE')

    def logConsumer(self):
        self.warnings = []
        while True:
            stream, line = yield
            if line.startswith('build succeeded') or \
               line.startswith('no targets are out of date.'):
                self.success = True
            else:
                for msg in self._msgs:
                    if msg in line:
                        self.warnings.append(line)

    def createSummary(self, log):
        if self.warnings:
            self.addCompleteLog('warnings', "\n".join(self.warnings))

        self.step_status.setStatistic('warnings', len(self.warnings))

    def evaluateCommand(self, cmd):
        if self.success:
            if not self.warnings:
                return SUCCESS
            return WARNINGS
        return FAILURE

    def describe(self, done=False):
        if not done:
            return ["building"]

        return [self.name, '%d warnings' % len(self.warnings)]
