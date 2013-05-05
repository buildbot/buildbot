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
import itertools
from collections import Counter

from buildbot.process.buildstep import LogLineObserver
from buildbot.steps.shell import Compile
from buildbot.status.results import SUCCESS, FAILURE, SKIPPED

class XcodeBuild(Compile):
    progressMetrics = Compile.progressMetrics + ("targets",)

    def __init__(self, project=None, scheme=None, target=None, 
                 configuration=None, sdk=None, arch=None,
                 actions=['clean', 'build', 'install'],
                 extraArgs=[], name=None,
                 **kwargs):

        cmd = ['xcodebuild'] + actions

        if project:
            cmd.extend(['-project', project])
        if scheme:
            cmd.extend(['-scheme', scheme])
        if target:
            cmd.extend(['-target', target])
        if configuration:
            cmd.extend(['-configuration', configuration])
        if sdk:
             cmd.extend(['-sdk', sdk])
        for a in (arch or []):
            cmd.extend(['-arch', a]) 

        cmd.extend(extraArgs)

        if not name:
            # generate as interesting a name as we can, filtering out non-strings (and '/' which mess up URLs)
            name = ['xcodebuild', project, scheme, target]
            name = [x.replace('/','-') for x in name if isinstance(x, str)]
            name = ' '.join(name)

        Compile.__init__(self, name=name,
                   description=["building"],
                   descriptionDone=["build"],
                   command=cmd,
                   **kwargs)

    def setupLogfiles(self, cmd, logfiles):
        self.summarizer = XcodebuildSummarizer(self)
        self.addLogObserver('stdio', self.summarizer)

    def createWarningsLog(self, log):
        self.warnCount = self.summarizer.getCountForSummaryType('warning')


class HtmlLogSummaryWriter(object):
    HTML_HEADER = """
    <html>
    <style type="text/css">
        .lineno {
            background-color: #ececec;
            color: #aaa;
            padding: 0 6px;
            border-right: 1px solid #ddd;
            text-align: right;
            cursor: pointer;
        }

        .line, .header, .lineno {
            font-family: Consolas, "Liberation Mono", Courier, monospace;
            white-space: pre;
        }

        .header-info {
            font-weight: bold;
        }
        .header-warning {
            font-weight: bold;
            background-color: orange;
        }
        .header-error {
            font-weight: bold;
            background-color: red;
        }

    </style>
    <body>
    <table class='summary'>
    <tbody>
    """

    HTML_FOOTER = """
    </tbody>
    </table>
    </body>
    </html>
    """

    HTML_HEADER_LINE = """<tr><td class='header header-%(summaryType)s' colspan=2>%(line)s</td></tr>\n"""
    HTML_INFO_LINE = """<tr><td class='lineno'>%(lineno)s</td><td class='line'>%(line)s</td></tr>\n"""

    def __init__(self, step):
        self.step = step
        self.chunks = []

    def writeSummary(self, summary):
        if 'header' in summary:
            summaryType = summary.get('type', '')
            self.chunks.append(self.HTML_HEADER_LINE % { 'summaryType': summaryType, 'line': summary['header']})

        for linedict in summary.get('lines', []):
            lineno = linedict.get('lineno', '')
            line   = linedict['line']
            self.chunks.append(self.HTML_INFO_LINE % { 'lineno': lineno, 'line': line})

    def finish(self):
        htmlIter = itertools.chain(
            (self.HTML_HEADER,), 
            self.chunks, 
            (self.HTML_FOOTER,)
        )

        html = '\n'.join(htmlIter)

        self.step.addHTMLLog("summary.html", html)


class LogFileSummarizer(LogLineObserver):
    """A log observer that generates a summary log file.

    lineConsumer is a generator that will be sent each log line as it happens.
    As "interesting" lines are consumed, the lineConsumer can call 'reportSummary'
    with a summary dictionary with optional keys:
        'type': the general category of this summary.
        'header': a lead-in line to introduce this summary dictionary
        'lines': a list of log lines that make up this summary
        'progress': report progress to the build step; should be a string with the
            metric name

    Each summary dictionary will get processed, keeping a running count of the 'type'
    seen (eg, for warning counting) as well as a progress counter for the progress metrics.
    """

    def __init__(self, step, lineConsumer):
        LogLineObserver.__init__(self)

        self.lineConsumer = lineConsumer

        self.summaryTypeCounter = Counter()
        self.progressCounter = Counter()

        self.lineno = 1

        self.summaryWriter = HtmlLogSummaryWriter(step)

    def setLog(self, loog):
        # start the geneartor/reset the generator
        self.lineConsumer.send(None)
        LogLineObserver.setLog(self, loog)

    def outLineReceived(self, line):
        """Process a received stdout line."""
        self.lineConsumer.send({ 'lineno': self.lineno, 'line': line })
        self.lineno += 1

    def errLineReceived(self, line):
        """Process a received stderr line."""
        self.lineConsumer.send({ 'line': line })

    def logFinished(self):
         # signal the log file is complete and give it a chance
        # to push out anything else that might still need reported
        try:
            self.lineConsumer.send(None)
        except StopIteration:
            pass

        self.summaryWriter.finish()

    def getCountForSummaryType(self, summaryType):
        return self.summaryTypeCounter[summaryType]

    def reportSummary(self, summary):
        summaryType = summary.get('type', '')
        self.summaryTypeCounter[summaryType] += 1
   
        if 'progress' in summary:
            progress = summary['progress']
            self.progressCounter[progress] += 1
            self.step.setProgress(progress, self.progressCounter[progress])

        self.summaryWriter.writeSummary(summary)


class WarningSummarizer(LogFileSummarizer):

    def createSummaryFooter(self):
        # generate a summary footer
        footer = { 
            'type': 'header', 
            'lines': [] 
        }

        warningCount = self.getCountForSummaryType('warning')
        errorCount   = self.getCountForSummaryType('error')

        if warningCount:
            footer['lines'].append({'line': "%d warnings detected" % warningCount})

            stepWarningCount = self.step.step_status.getStatistic('warnings', 0)
            self.step.step_status.setStatistic('warnings', stepWarningCount + warningCount)

            buildWarningCount = self.step.getProperty("warnings-count", 0)
            self.step.setProperty("warnings-count", buildWarningCount + warningCount, 'WarningSummarizer')

        if errorCount:
            footer['lines'].append({'line': "%d errors" % errorCount})

            stepErrorCount = self.step.step_status.getStatistic('errors', 0)
            self.step.step_status.setStatistic('errors detected', stepErrorCount + errorCount)

        if not footer['lines']:
            footer['lines'].append({'line': "No warnings or errors detected"})

        self.reportSummary(footer)

    def logFinished(self):
        self.createSummaryFooter()
        LogFileSummarizer.logFinished(self)


class XcodebuildSummarizer(WarningSummarizer):
    def __init__(self, step, lineConsumer=None, **kwargs):
        if not lineConsumer:
            lineConsumer = xcodebuildLineSummarizer(self.reportSummary)

        WarningSummarizer.__init__(self,
                                   step=step,
                                   lineConsumer=lineConsumer, 
                                   **kwargs)

def clangLineSummarizer(addSummaryFunctor):
    CLANG_DIAG_REPORT  = re.compile(r"(?P<path>.*?(?P<file>[^/]+)):(?P<line>\d+):(?P<col>\d+): (?P<type>warning|fatal error|error|note): (?P<text>.*)")
    CLANG_DIAG_SUMMARY = re.compile(r"\d+ (error|warning)s? generated.")

    LD_DIAG_REPORT =       re.compile(r"ld: (?P<warning>warning: )?.*")

    # This python generator that receives log lines as input and consumes 
    # them, calling 'addSummaryFunctor' whenever an issue or other 
    # interesting information has been detected.
    #
    # This is implemented as a generator so that we can maintain a simple state
    # machine. For example, some clang errors/warnings are followed by helpful
    # 'note' lines, which we want to collect as well.

    summaryLines = None
    while 1:
        # yields True if we're currently enjoying the lines we're getting
        linedict = yield (summaryLines is not None)

        # sending in "None" is a way to signal a clang build is complete
        if linedict is None:
            if summaryLines:
                addSummaryFunctor(summaryLines)
                summaryLines = None
            continue

        line = linedict['line']

        # check if it's a warning/error/note line
        m = CLANG_DIAG_REPORT.match(line)
        if m:
            summaryType = m.group('type')
            if summaryType=='note':
                # a 'note' must follow a error or warning, so we expect to
                # just append to a prior interest group
                assert summaryLines is not None
            else:
                # close out anything prior
                if summaryLines:
                    addSummaryFunctor(summaryLines)

                if summaryType == 'fatal error':
                    summaryType = 'error'

                summaryLines = {
                    'header': "%(type)s in %(file)s:%(line)s: %(text)s" % m.groupdict(),
                    'type': summaryType, 
                    'lines': [] 
                }

            summaryLines['lines'].append(linedict)
            continue

        # builds that have war ns or errors end in a summary line
        m = CLANG_DIAG_SUMMARY.match(line)
        if m:
            if summaryLines:
                addSummaryFunctor(summaryLines)

            summaryLines = { 
                'type': 'info', 
                'lines': [ linedict ] 
            }
            continue

        # catch ld errors
        m = LD_DIAG_REPORT.match(line)
        if m:
            if summaryLines:
                addSummaryFunctor(summaryLines)

            summaryLines = { 
                'type': 'warning', 
                'lines': [ linedict ] 
            }
            continue

        # once we hit a blank line, we're done
        if not line.strip():
            if summaryLines:
                addSummaryFunctor(summaryLines)
                summaryLines = None
            continue

        # any other lines are collected if our 'summaryLines' group is active
        # if possible (this expects that we'll hit some line to close the
        # prior group)
        if summaryLines is not None:
            summaryLines['lines'].append(linedict)


def genericSummarizer(addSummaryFunctor):
    """A consumer that just consumes up to the next blank line"""
    value = False
    while 1:
        # yields True if we're currently enjoying the lines we're getting
        linedict = yield value
        if linedict is None:
            value = False
        else:
            line = linedict.get('line','')
            value = False if not line.strip() else True
        

XcodebuildBuilderSummaryFactory = {
    'default':  genericSummarizer,
    'CompileC': clangLineSummarizer,
    'Ld':       clangLineSummarizer,
}

def xcodebuildLineSummarizer(addSummaryFunctor, builderSummaryFactory=XcodebuildBuilderSummaryFactory):
    # each build phase:
    #    starts with a line like "=== blah blah ==="
    #    ends with a line like "** blah blah **"
    XCODE_BUILD_PHASE_START = re.compile(r"=== .* ===")

    # xcode build steps:
    #     start with a word in the first column
    #     print some lines with leading spaces (like the build commands)
    #     optionally print output from the build command (like compiler warnings)
    #     end with a blank line
    XCODE_STEP_START = re.compile(r"(?P<type>\S+) (.*)")

    # build settings:
    XCODE_BUILD_SETTINGS_START = re.compile("Build settings from command line:")
    XCODE_BUILD_SETTINGS_END   = re.compile(r"^\S*$") # an empty line

    # when a build fails we get lines that start and end like this:
    XCODE_BUILD_FAILED_START = re.compile(r"\*\* BUILD FAILED \*\*")
    XCODE_BUILD_FAILED_END   = re.compile(r"\d+ failures?")

    # Xcode makes calls to various tools (eg, compiler, linker) as part of the
    # build process. We delegate to summarizers for those build types. We will
    # have them report their summaries into a list, and after we stop delegating
    # we will check this list and push them to our summarizer.
    builderSummaryLines = []
    
    builderSummarizers = {}
    for builder, factory in builderSummaryFactory.iteritems():
        summarizer = factory(builderSummaryLines.append)
        summarizer.send(None)
        builderSummarizers[builder] = summarizer

    genericSummarizer = builderSummarizers['default']

    # This python generator that receives log lines as input and consumes 
    # them, calling addSummaryFunctor whenever an issue or other 
    # interesting information has been detected.
    #
    # This is implemented as a generator so that we can maintain a simple state
    # machine. For example, some clang errors/warnings are followed by helpful
    # 'note' lines, which we want to collect as well.

    summaryLines = None
    while 1:
        # yields True if we're currently enjoying the lines we're getting
        linedict = yield (summaryLines is not None)

        # sending in "None" is a way to signal a clang build is complete
        if linedict is None:
            # clear out the summarizers too:
            for name, s in builderSummarizers.iteritems():
                s.send(None)

            if summaryLines:
                addSummaryFunctor(summaryLines)
                summaryLines = None
            continue

        line = linedict['line']

        # a build phase change:
        #    just push out the line as something always interesting
        m = XCODE_BUILD_PHASE_START.match(line)
        if m:
            # close out anything prior
            if summaryLines:
                addSummaryFunctor(summaryLines)
            summaryLines = { 
                'type': 'info',
                'progress': 'targets',  # build phases are good markers of progress
                'lines': [linedict] 
            }
            continue


        # a report of the build settings
        #    consume everything up to the 'end' marker
        m = XCODE_BUILD_SETTINGS_START.match(line)
        if m:
            # close out anything prior
            if summaryLines:
                addSummaryFunctor(summaryLines)
            summaryLines = { 
                'type': 'info', 
                'lines': [linedict] 
            }

            # capture all lines until we hit the "end" marker for the settings report
            while 1:
                linedict = yield True

                if not linedict:
                    break

                summaryLines['lines'].append(linedict)

                m = XCODE_BUILD_SETTINGS_END.match(linedict['line'])
                if m:
                    break
                
            addSummaryFunctor(summaryLines)
            summaryLines = None
            continue


        # a report of other types of build failures
        #    consume everything up to the 'end' marker
        m = XCODE_BUILD_FAILED_START.match(line)
        if m:
            # close out anything prior
            if summaryLines:
                addSummaryFunctor(summaryLines)
            summaryLines = { 
                'type': 'error', 
                'lines': [] 
            }

            # capture all lines until we hit the "end" marker
            while 1:
                summaryLines['lines'].append(linedict)
                
                linedict = yield True
                m = XCODE_BUILD_FAILED_END.match(line)
                if m:
                    break

            addSummaryFunctor(summaryLines)
            summaryLines = None
            continue

        # Otherwise, we might be reporting a build step:
        m = XCODE_STEP_START.match(line)
        if m:
            # close out anything prior
            if summaryLines:
                addSummaryFunctor(summaryLines)

            summaryLines = { 
                'header': "Context for the next issues reported:",
                'type': 'info', 
                'lines': [linedict] 
            }

            builder = builderSummarizers.get(m.group('type'), genericSummarizer)
            count = 0
            while 1:
                linedict = yield True
                consumed = builder.send(linedict)

                # if the line was interesting, keep going!
                if consumed:
                    continue 

                # if the line was not interesting, it might be time to move on to something
                # else; xcodebuild uses blank lines between build steps, so if we're there
                # let's get out and see what's next
                if not linedict or not linedict['line'].strip(): # a blank line ends it
                    break

            # reset the builder
            builder.send(None)

            # only print something if the builder found it interesting:
            if builderSummaryLines:
                addSummaryFunctor(summaryLines)

                for s in builderSummaryLines:
                    addSummaryFunctor(s)

                del builderSummaryLines[:] # XX: keep same list object, just clear it

            summaryLines = None
            continue

        # once we hit a blank line, we're done
        if not line.strip():
            if summaryLines:
                addSummaryFunctor(summaryLines)
                summaryLines = None
            continue

        # any other lines are collected if our 'summaryLines' group is active
        # if possible (this expects that we'll hit some line to close the
        # prior group)
        if summaryLines is not None:
            summaryLines['lines'].append(linedict)
