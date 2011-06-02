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


from buildbot.steps.shell import ShellCommand
from buildbot.status.results import SUCCESS, FAILURE

class SubunitShellCommand(ShellCommand):
    """A ShellCommand that sniffs subunit output.
    """

    def __init__(self, failureOnNoTests=False, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.failureOnNoTests = failureOnNoTests
        # importing here gets around an import loop
        from buildbot.process import subunitlogobserver
        self.ioObverser = subunitlogobserver.SubunitLogObserver()
        self.addLogObserver('stdio', self.ioObverser)
        self.progressMetrics = self.progressMetrics + ('tests', 'tests failed')
    def commandComplete(self, cmd):
        # figure out all statistics about the run
        ob = self.ioObverser
        failures = len(ob.failures)
        errors = len(ob.errors)
        skips = len(ob.skips)
        total = ob.testsRun

        count = failures + errors

        text = [self.name]
        text2 = ""

        if not count:
            results = SUCCESS
            if total:
                text += ["%d %s" % \
                          (total,
                          total == 1 and "test" or "tests"),
                          "passed"]
            elif self.failureOnNoTests:
                results = FAILURE
                text += ["no test is found"]
            else:
                text += ["no tests", "run"]
        else:
            results = FAILURE
            text.append("Total %d test(s)" % total)
            if failures:
                text.append("%d %s" % \
                            (failures,
                             failures == 1 and "failure" or "failures"))
            if errors:
                text.append("%d %s" % \
                            (errors,
                             errors == 1 and "error" or "errors"))
            text2 = "%d tes%s" % (count, (count == 1 and 't' or 'ts'))


        if skips:
            text.append("%d %s" %  (skips,
                         skips == 1 and "skip" or "skips"))

        #TODO: expectedFailures/unexpectedSuccesses

        self.results = results
        self.text = text
        self.text2 = [text2]
        
    def evaluateCommand(self, cmd):
        if cmd.rc != 0:
            return FAILURE
        return self.results

    def createSummary(self, loog):
        ob = self.ioObverser
        problems = ""
        for test, err in ob.errors + ob.failures:
            problems += "%s\n%s" % (test.id(), err)
        if problems:
            self.addCompleteLog("problems", problems)
        warnings = ob.warningio.getvalue()
        if warnings:
            self.addCompleteLog("warnings", warnings)

    def getText(self, cmd, results):
        return self.text
    def getText2(self, cmd, results):
        return self.text2
