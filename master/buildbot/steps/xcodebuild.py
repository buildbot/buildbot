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
from collections import Counter

from buildbot.process.buildstep import LogLineObserver
from buildbot.steps.shell import Compile
from buildbot.status.results import SUCCESS, FAILURE, SKIPPED

class XcodeBuild(Compile):
    progressMetrics = Compile.progressMetrics + ("targets",)

    def __init__(self, project=None, scheme=None, target=None, 
                 configuration=None, sdk=None, arch=None,
                 actions=['clean', 'build', 'install'],
                 extra_args=[], name=None,
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

        cmd.extend(extra_args)

        if not name:
            # generate as interesting a name as we can, filtering out non-strings (and '/' which mess up URLs)
            name = ['xcodebuild', project, scheme, target]
            name = [x.replace('/','-') for x in name if isinstance(x, basestring)]

        Compile.__init__(self, name=name,
                   description=["building"],
                   descriptionDone=["build"],
                   command=cmd,
                   **kwargs)

    def setupLogfiles(self, cmd, logfiles):
        summary = self.addLog("summary")
        self.summarizer = XcodebuildSummarizer(summary)
        self.addLogObserver('stdio', self.summarizer)

    def createWarningsLog(self, log):
        self.warnCount = self.summarizer.getCount('warning')


class LogFileSummarizer(LogLineObserver):
    """A log observer that generates a summary log file.

    lineConsumer is a generator that will be sent each log line as it happens.
    As "interesting" lines are consumed, the lineConsumer can call 'reportSummary'
    with a summary dictionary with optional keys:
        'kind': the general category of this summary.
        'header': a lead-in line to introduce this summary dictionary
        'lines': a list of log lines that make up this summary
        'progress': report progress to the build step; should be a string with the
            metric name

    Each summary dictionary will get processed, keeping a running count of the 'kind'
    seen (eg, for warning counting) as well as a progress counter for the progress metrics.
    """

    def __init__(self, summaryLogFile, lineConsumer):
        LogLineObserver.__init__(self)

        self.summaryLogFile = summaryLogFile
        self.lineConsumer = lineConsumer

        self.kindCounter = Counter()
        self.progressCounter = Counter()

    def outLineReceived(self, line):
        """Process a received stdout line."""
        self.lineConsumer.send(line)

    def errLineReceived(self, line):
        """Process a received stderr line."""
        self.lineConsumer.send(line)

    def logFinished(self):
         # signal the log file is complete and give it a chance
        # to push out anything else that might still need reported
        try:
            self.lineConsumer.send(None)
        except StopIteration:
            pass

    def reportSummary(self, summary):
        kind = summary.get('kind', '')
        self.kindCounter[kind] += 1
     
        writeLog    = self.summaryLogFile.addStdout
        writeHeader = self.summaryLogFile.addHeader
   
        if kind=='error':
            # write the lead line as error
            writeHeader = self.summaryLogFile.addStderr
        elif kind=='header':
            # write all lines as header
            writeLog = writeHeader

        if 'progress' in summary:
            progress = summary['progress']
            self.progressCounter[progress] += 1
            self.step.setProgress(progress, self.progressCounter[progress])

        if 'header' in summary:
            writeHeader(summary['header'] + '\n')

        for line in summary.get('lines', []):
            writeLog(line + '\n')


class WarningSummarizer(LogFileSummarizer):

    def getCount(self, kind):
        return self.kindCounter[kind]

    def logFinished(self):
        LogFileSummarizer.logFinished(self)

        # generate a summary footer
        footer = { 
            'kind': 'header', 
            'lines': [] 
        }

        warning_count = self.getCount('warning')
        error_count = self.getCount('error')

        if warning_count:
            footer['lines'].append("%d warnings detected" % warning_count)

            step_warning_count = self.step.step_status.getStatistic('warnings', 0)
            self.step_status.setStatistic('warnings', step_warning_count + warning_count)

            build_warning_count = self.step.getProperty("warnings-count", 0)
            self.setProperty("warnings-count", build_warning_count + warning_count, 'WarningSummarizer')

        if error_count:
            footer['lines'].append("%d errors" % error_count)

            step_error_count = self.step.step_status.getStatistic('errors', 0)
            self.step_status.setStatistic('errors detected', step_error_count + error_count)

        if not error_count and not warning_count:
            footer['lines'].append("No warnings or errors detected")            

        self.reportSummary(footer)


class XcodebuildSummarizer(WarningSummarizer):
    def __init__(self, summaryLogFile, lineConsumer=None, **kwargs):
        if not lineConsumer:
            lineConsumer = createXcodebuildLineSummarizer(self.reportSummary)

        LogFileSummarizer.__init__(self, 
                                   summaryLogFile=summaryLogFile,
                                   lineConsumer=lineConsumer, 
                                   **kwargs)

def createClangLineSummarizer(addSummary):
    clang_diag =    re.compile(r"(?P<path>.*?(?P<file>[^/]+)):(?P<line>\d+):(?P<col>\d+): (?P<kind>warning|error|note): (?P<text>.*)")
    clang_summary = re.compile(r"\d+ (error|warning)s? generated.")

    ld_diag =       re.compile(r"ld: (?P<warning>warning: )?.*")

    ld_missing_symbols_start = re.compile("Undefined symbols for architecture .*:")
    ld_missing_symbols_end   = re.compile("ld: symbol(s) not found for architecture .*")

    def consumer():
        # This python generator that receives log lines as input and consumes 
        # them, calling 'addSummary' whenever an issue or other 
        # interesting information has been detected.
        #
        # This is implemented as a generator so that we can maintain a simple state
        # machine. For example, some clang errors/warnings are followed by helpful
        # 'note' lines, which we want to collect as well.

        summaryLines = None
        while 1:
            # yields True if we're currently enjoying the lines we're getting
            line = yield (summaryLines is not None)

            # sending in "None" is a way to signal a clang build is complete
            if line is None:
                if summaryLines:
                    addSummary(summaryLines)
                    summaryLines = None
                continue

            # check if it's a warning/error/note line
            m = clang_diag.match(line)
            if m:
                if m.group('kind')=='note':
                    # a 'note' must follow a error or warning, so we expect to
                    # just append to a prior interest group
                    assert summaryLines is not None
                else:
                    # close out anything prior
                    if summaryLines:
                        addSummary(summaryLines)
                    summaryLines = {
                        'header': "%(kind)s in %(file)s:%(line)s: %(text)s" % m.groupdict(),
                        'kind': m.group('kind'), 
                        'lines': [] 
                    }

                summaryLines['lines'].append(line)
                continue

            # builds that have warnings or errors end in a summary line
            m = clang_summary.match(line)
            if m:
                if summaryLines:
                    addSummary(summaryLines)

                summaryLines = { 
                    'header': line,  # the 'header' is the line itself
                    'kind': 'info', 
                    'lines': [] 
                }
                continue

            # catch ld errors
            m = ld_diag.match(line)
            if m:
                if summaryLines:
                    addSummary(summaryLines)

                summaryLines = { 
                    'header': line,  # the 'header' is the line itself
                    'kind': 'warning', 
                    'lines': [] 
                }
                continue

            # once we hit a blank line, we're done
            if not line.strip():
                if summaryLines:
                    addSummary(summaryLines)
                    summaryLines = None
                continue

            # any other lines are collected if our 'summaryLines' group is active
            # if possible (this expects that we'll hit some line to close the
            # prior group)
            if summaryLines is not None:
                summaryLines['lines'].append(line)

    consumer = consumer()
    next(consumer) # start it
    return consumer

def createGenericSummarizer(addSummary):
    """A consumer that just consumes up to the next blank line"""
    def consumer():
        value = False
        while 1:
            # yields True if we're currently enjoying the lines we're getting
            line = yield value
            if line is not None:
                line = line.strip()
            value = False if not line else True

    consumer = consumer()
    next(consumer) # start it
    return consumer

def createXcodebuildLineSummarizer(addSummary):
    # each build phase:
    #    starts with a line like "=== blah blah ==="
    #    ends with a line like "** blah blah **"
    xcode_build_phase_start = re.compile(r"=== .* ===")

    # xcode build steps:
    #     start with a word in the first column
    #     print some lines with leading spaces (like the build commands)
    #     optionally print output from the build command (like compiler warnings)
    #     end with a blank line
    xcode_step_line_start = re.compile(r"(?P<kind>\S+) (.*)")
    xcode_step_output_start = re.compile(r"\S.*")
    xcode_step_line_end   = re.compile(r"")

    # build settings:
    xcode_build_settings_start = re.compile("Build settings from command line:")
    xcode_build_settings_end   = re.compile("") # an empty line

    # when a build fails we get lines that start and end like this:
    xcode_build_failed_start = re.compile(r"\*\* BUILD FAILED \*\*")
    xcode_build_failed_end   = re.compile(r"\d+ failures?")

    xcode_dep_cycle_detected = re.compile(r"Dependency cycle for target.*")

    generic_error_search_line   = re.compile("error[: ]")
    generic_warning_search_line = re.compile("warning[: ]")

    # Xcode makes calls to various tools (eg, compiler, linker) as part of the
    # build process. We delegate to summarizers for those build types. We will
    # have them report their summaries into a list, and after we stop delegating
    # we will check this list and push them to our summarizer.
    builderSummaryLines = []
    
    genericSummarizer = createGenericSummarizer(builderSummaryLines.append)
    clangSummarizer = createClangLineSummarizer(builderSummaryLines.append)

    builderSummarizers = {
        'CompileC': clangSummarizer,
        'Ld':       clangSummarizer,
    }

    def consumer():
        # This python generator that receives log lines as input and consumes 
        # them, calling addSummary whenever an issue or other 
        # interesting information has been detected.
        #
        # This is implemented as a generator so that we can maintain a simple state
        # machine. For example, some clang errors/warnings are followed by helpful
        # 'note' lines, which we want to collect as well.

        summaryLines = None
        while 1:
            # yields True if we're currently enjoying the lines we're getting
            line = yield (summaryLines is not None)

            # sending in "None" is a way to signal a clang build is complete
            if line is None:
                # clear out the summarizers too:
                for name, s in builderSummarizers.iteritems():
                    s.send(None)

                if summaryLines:
                    addSummary(summaryLines)
                    summaryLines = None
                continue

            # a build phase change:
            #    just push out the line as something always interesting
            m = xcode_build_phase_start.match(line)
            if m:
                # close out anything prior
                if summaryLines:
                    addSummary(summaryLines)
                summaryLines = { 
                    'header': line,
                    'kind': 'info',
                    'progress': 'targets',  # build phases are good markers of progress
                    'lines': [] 
                }
                continue


            # a report of the build settings
            #    consume everything up to the 'end' marker
            m = xcode_build_settings_start.match(line)
            if m:
                # close out anything prior
                if summaryLines:
                    addSummary(summaryLines)
                summaryLines = { 
                    'header': line,  # the first line makes a nice header
                    'kind': 'info', 
                    'lines': [] 
                }

                # capture all lines until we hit the "end" marker for the settings report
                while 1:
                    line = yield True
                    m = xcode_build_settings_end.match(line)
                    if m:
                        break
                    summaryLines['lines'].append(line)
                    
                addSummary(summaryLines)
                summaryLines = None
                continue


            # a report of other kinds of build failures
            #    consume everything up to the 'end' marker
            m = xcode_build_failed_start.match(line)
            if m:
                # close out anything prior
                if summaryLines:
                    addSummary(summaryLines)
                summaryLines = { 
                    'kind': 'error', 
                    'lines': [] 
                }

                # capture all lines until we hit the "end" marker
                while 1:
                    summaryLines['lines'].append(line)
                    
                    line = yield True
                    m = xcode_build_failed_end.match(line)
                    if m:
                        break

                addSummary(summaryLines)
                summaryLines = None
                continue

            # Otherwise, we might be reporting a build step:
            m = xcode_step_line_start.match(line)
            if m:
                # close out anything prior
                if summaryLines:
                    addSummary(summaryLines)

                summaryLines = { 
                    'kind': 'info', 
                    'lines': [line] 
                }

                builder = builderSummarizers.get(m.group('kind'), genericSummarizer)
                count = 0
                while 1:
                    line = yield True
                    consumed = builder.send(line)

                    # if the line was interesting, keep going!
                    if consumed:
                        continue 

                    # if the line was not interesting, it might be time to move on to something
                    # else; xcodebuild uses blank lines between build steps, so if we're there
                    # let's get out and see what's next
                    if not line or not line.strip(): # a blank line ends it
                        break

                # reset the builder
                builder.send(None)

                # only print something if the builder found it interesting:
                if builderSummaryLines:
                    addSummary(summaryLines)

                    for s in builderSummaryLines:
                        addSummary(s)

                    del builderSummaryLines[:] # XX: keep same list object, just clear it

                summaryLines = None
                continue

            # once we hit a blank line, we're done
            if not line.strip():
                if summaryLines:
                    addSummary(summaryLines)
                    summaryLines = None
                continue

            # any other lines are collected if our 'summaryLines' group is active
            # if possible (this expects that we'll hit some line to close the
            # prior group)
            if summaryLines is not None:
                summaryLines['lines'].append(line)


    consumer = consumer()
    next(consumer) # start it
    return consumer
