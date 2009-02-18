
from buildbot.status.builder import SUCCESS, FAILURE, WARNINGS
from buildbot.steps.shell import ShellCommand
import re

try:
    import cStringIO
    StringIO = cStringIO.StringIO
except ImportError:
    from StringIO import StringIO


class BuildEPYDoc(ShellCommand):
    name = "epydoc"
    command = ["make", "epydocs"]
    description = ["building", "epydocs"]
    descriptionDone = ["epydoc"]

    def createSummary(self, log):
        import_errors = 0
        warnings = 0
        errors = 0

        for line in StringIO(log.getText()):
            if line.startswith("Error importing "):
                import_errors += 1
            if line.find("Warning: ") != -1:
                warnings += 1
            if line.find("Error: ") != -1:
                errors += 1

        self.descriptionDone = self.descriptionDone[:]
        if import_errors:
            self.descriptionDone.append("ierr=%d" % import_errors)
        if warnings:
            self.descriptionDone.append("warn=%d" % warnings)
        if errors:
            self.descriptionDone.append("err=%d" % errors)

        self.import_errors = import_errors
        self.warnings = warnings
        self.errors = errors

    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
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
    flunkingIssues = ["undefined"] # any pyflakes lines like this cause FAILURE

    MESSAGES = ("unused", "undefined", "redefs", "import*", "misc")

    def createSummary(self, log):
        counts = {}
        summaries = {}
        for m in self.MESSAGES:
            counts[m] = 0
            summaries[m] = []

        first = True
        for line in StringIO(log.getText()).readlines():
            # the first few lines might contain echoed commands from a 'make
            # pyflakes' step, so don't count these as warnings. Stop ignoring
            # the initial lines as soon as we see one with a colon.
            if first:
                if line.find(":") != -1:
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
            else:
                m = "misc"
            summaries[m].append(line)
            counts[m] += 1

        self.descriptionDone = self.descriptionDone[:]
        for m in self.MESSAGES:
            if counts[m]:
                self.descriptionDone.append("%s=%d" % (m, counts[m]))
                self.addCompleteLog(m, "".join(summaries[m]))
            self.setProperty("pyflakes-%s" % m, counts[m], "pyflakes")
        self.setProperty("pyflakes-total", sum(counts.values()), "pyflakes")


    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        for m in self.flunkingIssues:
            if self.getProperty("pyflakes-%s" % m):
                return FAILURE
        if self.getProperty("pyflakes-total"):
            return WARNINGS
        return SUCCESS

class PyLint(ShellCommand):
    '''A command that knows about pylint output.
    It's a good idea to add --output-format=parseable to your
    command, since it includes the filename in the message.
    '''
    name = "pylint"
    description = ["running", "pylint"]
    descriptionDone = ["pylint"]

    # Using the default text output, the message format is :
    # MESSAGE_TYPE: LINE_NUM:[OBJECT:] MESSAGE
    # with --output-format=parseable it is: (the outer brackets are literal)
    # FILE_NAME:LINE_NUM: [MESSAGE_TYPE[, OBJECT]] MESSAGE
    # message type consists of the type char and 4 digits
    # The message types:

    MESSAGES = {
            'C': "convention", # for programming standard violation
            'R': "refactor", # for bad code smell
            'W': "warning", # for python specific problems
            'E': "error", # for much probably bugs in the code
            'F': "fatal", # error prevented pylint from further processing.
            'I': "info",
        }

    flunkingIssues = ["F", "E"] # msg categories that cause FAILURE

    _re_groupname = 'errtype'
    _msgtypes_re_str = '(?P<%s>[%s])' % (_re_groupname, ''.join(MESSAGES.keys()))
    _default_line_re = re.compile(r'%s\d{4}: *\d+:.+' % _msgtypes_re_str)
    _parseable_line_re = re.compile(r'[^:]+:\d+: \[%s\d{4}[,\]] .+' % _msgtypes_re_str)

    def createSummary(self, log):
        counts = {}
        summaries = {}
        for m in self.MESSAGES:
            counts[m] = 0
            summaries[m] = []

        line_re = None # decide after first match
        for line in StringIO(log.getText()).readlines():
            if not line_re:
                # need to test both and then decide on one
                if self._parseable_line_re.match(line):
                    line_re = self._parseable_line_re
                elif self._default_line_re.match(line):
                    line_re = self._default_line_re
                else: # no match yet
                    continue
            mo = line_re.match(line)
            if mo:
                msgtype = mo.group(self._re_groupname)
                assert msgtype in self.MESSAGES
            summaries[msgtype].append(line)
            counts[msgtype] += 1

        self.descriptionDone = self.descriptionDone[:]
        for msg, fullmsg in self.MESSAGES.items():
            if counts[msg]:
                self.descriptionDone.append("%s=%d" % (fullmsg, counts[msg]))
                self.addCompleteLog(fullmsg, "".join(summaries[msg]))
            self.setProperty("pylint-%s" % fullmsg, counts[msg])
        self.setProperty("pylint-total", sum(counts.values()))

    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        for msg in self.flunkingIssues:
            if self.getProperty("pylint-%s" % self.MESSAGES[msg]):
                return FAILURE
        if self.getProperty("pylint-total"):
            return WARNINGS
        return SUCCESS

