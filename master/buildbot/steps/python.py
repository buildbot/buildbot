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

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results


class BuildEPYDoc(buildstep.ShellMixin, buildstep.BuildStep):
    name = "epydoc"
    command = ["make", "epydocs"]
    description = "building epydocs"
    descriptionDone = "epydoc"

    def __init__(self, **kwargs):
        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)
        self.addLogObserver('stdio', logobserver.LineConsumerLogObserver(self._log_consumer))

    def _log_consumer(self):
        self.import_errors = 0
        self.warnings = 0
        self.errors = 0

        while True:
            _, line = yield
            if line.startswith("Error importing "):
                self.import_errors += 1
            if line.find("Warning: ") != -1:
                self.warnings += 1
            if line.find("Error: ") != -1:
                self.errors += 1

    def getResultSummary(self):
        summary = ' '.join(self.descriptionDone)
        if self.import_errors:
            summary += f" ierr={self.import_errors}"
        if self.warnings:
            summary += f" warn={self.warnings}"
        if self.errors:
            summary += f" err={self.errors}"
        if self.results != SUCCESS:
            summary += f' ({Results[self.results]})'
        return {'step': summary}

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        if cmd.didFail():
            return FAILURE
        if self.warnings or self.errors:
            return WARNINGS
        return SUCCESS


class PyFlakes(buildstep.ShellMixin, buildstep.BuildStep):
    name = "pyflakes"
    command = ["make", "pyflakes"]
    description = "running pyflakes"
    descriptionDone = "pyflakes"
    flunkOnFailure = False

    # any pyflakes lines like this cause FAILURE
    _flunkingIssues = ("undefined",)

    _MESSAGES = ("unused", "undefined", "redefs", "import*", "misc")

    def __init__(self, *args, **kwargs):
        # PyFlakes return 1 for both warnings and errors. We
        # categorize this initially as WARNINGS so that
        # evaluateCommand below can inspect the results more closely.
        kwargs['decodeRC'] = {0: SUCCESS, 1: WARNINGS}

        kwargs = self.setupShellMixin(kwargs)
        super().__init__(*args, **kwargs)

        self.addLogObserver('stdio', logobserver.LineConsumerLogObserver(self._log_consumer))

        counts = self.counts = {}
        summaries = self.summaries = {}
        for m in self._MESSAGES:
            counts[m] = 0
            summaries[m] = []

        # we need a separate variable for syntax errors
        self._hasSyntaxError = False

    def _log_consumer(self):
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

    def getResultSummary(self):
        summary = ' '.join(self.descriptionDone)
        for m in self._MESSAGES:
            if self.counts[m]:
                summary += f" {m}={self.counts[m]}"

        if self.results != SUCCESS:
            summary += f' ({Results[self.results]})'

        return {'step': summary}

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        # we log 'misc' as syntax-error
        if self._hasSyntaxError:
            yield self.addCompleteLog("syntax-error", "\n".join(self.summaries['misc']))
        else:
            for m in self._MESSAGES:
                if self.counts[m]:
                    yield self.addCompleteLog(m, "\n".join(self.summaries[m]))
                self.setProperty(f"pyflakes-{m}", self.counts[m], "pyflakes")
            self.setProperty("pyflakes-total", sum(self.counts.values()), "pyflakes")

        if cmd.didFail() or self._hasSyntaxError:
            return FAILURE
        for m in self._flunkingIssues:
            if m in self.counts and self.counts[m] > 0:
                return FAILURE
        if sum(self.counts.values()) > 0:
            return WARNINGS
        return SUCCESS


class PyLint(buildstep.ShellMixin, buildstep.BuildStep):

    '''A command that knows about pylint output.
    It is a good idea to add --output-format=parseable to your
    command, since it includes the filename in the message.
    '''
    name = "pylint"
    description = "running pylint"
    descriptionDone = "pylint"

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

    _msgtypes_re_str = f"(?P<errtype>[{''.join(list(_MESSAGES))}])"
    _default_line_re = re.compile(fr'^{_msgtypes_re_str}(\d+)?: *\d+(, *\d+)?:.+')
    _default_2_0_0_line_re = \
        re.compile(fr'^(?P<path>[^:]+):(?P<line>\d+):\d+: *{_msgtypes_re_str}(\d+)?:.+')
    _parseable_line_re = re.compile(
        fr'(?P<path>[^:]+):(?P<line>\d+): \[{_msgtypes_re_str}(\d+)?(\([a-z-]+\))?[,\]] .+')

    def __init__(self, store_results=True, **kwargs):
        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)
        self._store_results = store_results
        self.counts = {}
        self.summaries = {}

        for m in self._MESSAGES:
            self.counts[m] = 0
            self.summaries[m] = []

        self.addLogObserver('stdio', logobserver.LineConsumerLogObserver(self._log_consumer))

    # returns (message type, path, line) tuple if line has been matched, or None otherwise
    def _match_line(self, line):
        m = self._default_2_0_0_line_re.match(line)
        if m:
            try:
                line_int = int(m.group('line'))
            except ValueError:
                line_int = None
            return (m.group('errtype'), m.group('path'), line_int)

        m = self._parseable_line_re.match(line)
        if m:
            try:
                line_int = int(m.group('line'))
            except ValueError:
                line_int = None
            return (m.group('errtype'), m.group('path'), line_int)

        m = self._default_line_re.match(line)
        if m:
            return (m.group('errtype'), None, None)

        return None

    def _log_consumer(self):
        while True:
            stream, line = yield
            if stream == 'h':
                continue

            ret = self._match_line(line)
            if not ret:
                continue

            msgtype, path, line_number = ret

            assert msgtype in self._MESSAGES
            self.summaries[msgtype].append(line)
            self.counts[msgtype] += 1

            if self._store_results and path is not None:
                self.addTestResult(self._result_setid, line, test_name=None, test_code_path=path,
                                   line=line_number)

    def getResultSummary(self):
        summary = ' '.join(self.descriptionDone)
        for msg, fullmsg in sorted(self._MESSAGES.items()):
            if self.counts[msg]:
                summary += f" {fullmsg}={self.counts[msg]}"

        if self.results != SUCCESS:
            summary += f' ({Results[self.results]})'

        return {'step': summary}

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        for msg, fullmsg in sorted(self._MESSAGES.items()):
            if self.counts[msg]:
                yield self.addCompleteLog(fullmsg, "\n".join(self.summaries[msg]))
            self.setProperty(f"pylint-{fullmsg}", self.counts[msg], 'Pylint')
        self.setProperty("pylint-total", sum(self.counts.values()), 'Pylint')

        if cmd.rc & (self.RC_FATAL | self.RC_ERROR | self.RC_USAGE):
            return FAILURE

        for msg in self._flunkingIssues:
            if msg in self.counts and self.counts[msg] > 0:
                return FAILURE
        if sum(self.counts.values()) > 0:
            return WARNINGS
        return SUCCESS

    @defer.inlineCallbacks
    def addTestResultSets(self):
        if not self._store_results:
            return
        self._result_setid = yield self.addTestResultSet('Pylint warnings', 'code_issue', 'message')


class Sphinx(buildstep.ShellMixin, buildstep.BuildStep):

    ''' A Step to build sphinx documentation '''

    name = "sphinx"
    description = "running sphinx"
    descriptionDone = "sphinx"

    haltOnFailure = True

    def __init__(self, sphinx_sourcedir='.', sphinx_builddir=None,
                 sphinx_builder=None, sphinx='sphinx-build', tags=None,
                 defines=None, strict_warnings=False, mode='incremental', **kwargs):

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

        kwargs = self.setupShellMixin(kwargs)

        super().__init__(**kwargs)

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
                                f'{key}={defines[key] and 1 or 0}'])
            else:
                command.extend(['-D', f'{key}={defines[key]}'])

        if mode == 'full':
            command.extend(['-E'])  # Don't use a saved environment

        if strict_warnings:
            command.extend(['-W'])  # Convert warnings to errors

        command.extend([sphinx_sourcedir, sphinx_builddir])
        self.command = command

        self.addLogObserver('stdio', logobserver.LineConsumerLogObserver(self._log_consumer))

    _msgs = ('WARNING', 'ERROR', 'SEVERE')

    def _log_consumer(self):
        self.warnings = []
        next_is_warning = False

        while True:
            _, line = yield
            if line.startswith('build succeeded') or \
               line.startswith('no targets are out of date.'):
                self.success = True
            elif line.startswith('Warning, treated as error:'):
                next_is_warning = True
            else:
                if next_is_warning:
                    self.warnings.append(line)
                    next_is_warning = False
                else:
                    for msg in self._msgs:
                        if msg in line:
                            self.warnings.append(line)

    def getResultSummary(self):
        summary = f'{self.name} {len(self.warnings)} warnings'

        if self.results != SUCCESS:
            summary += f' ({Results[self.results]})'

        return {'step': summary}

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        if self.warnings:
            yield self.addCompleteLog('warnings', "\n".join(self.warnings))

        self.setStatistic('warnings', len(self.warnings))

        if self.success:
            if not self.warnings:
                return SUCCESS
            return WARNINGS
        return FAILURE
