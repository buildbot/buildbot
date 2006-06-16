

# test step.ShellCommand and the slave-side commands.ShellCommand

import sys
from twisted.trial import unittest
from buildbot.process.step import ShellCommand
from buildbot.slave.commands import SlaveShellCommand
from buildbot.twcompat import maybeWait
from buildbot.test.runutils import SlaveCommandTestBase

class SlaveSide(SlaveCommandTestBase, unittest.TestCase):
    def testOne(self):
        args = {
            'command': [sys.executable, "emit.py", "0"],
            'workdir': ".",
            }
        d = self.startCommand(SlaveShellCommand, args)
        d.addCallback(self.collectUpdates)
        def _check(logs):
            self.failUnlessEqual(logs['stdout'], "this is stdout\n")
            self.failUnlessEqual(logs['stderr'], "this is stderr\n")
        d.addCallback(_check)
        return maybeWait(d)

    # TODO: move test_slavecommand.Shell and .ShellPTY over here

    def _generateText(self, filename):
        lines = []
        for i in range(3):
            lines.append("this is %s %d\n" % (filename, i))
        return "".join(lines)

    def testLogFiles(self):
        # emitlogs.py writes one line per second to stdout and two logfiles,
        # for 3 seconds total.
        args = {
            'command': [sys.executable, "emitlogs.py"],
            'workdir': ".",
            'logfiles': {"log2": "log2.out",
                         "log3": "log3.out"},
            }
        d = self.startCommand(SlaveShellCommand, args)
        # after two seconds, there should be some data in the secondary
        # logfiles

        # TODO: I want to test that logfiles are being read in a timely
        # fashion. How can I do this and still have the tests be reliable
        # under load?

        d.addCallback(self.collectUpdates)
        def _check(logs):
            self.failUnlessEqual(logs['stdout'], self._generateText("stdout"))
            self.failUnlessEqual(logs[('log','log2')],
                                 self._generateText("log2"))
            self.failUnlessEqual(logs[('log','log3')],
                                 self._generateText("log3"))
        d.addCallback(_check)
        return maybeWait(d)
    testLogFiles.todo = "doesn't work yet"


def OFF_testLogfiles_1(self, res, ss):
    logs = {}
    for l in ss.getLogs():
        logs[l.getName()] = l
    self.failUnlessEqual(logs['stdio'].getText(),
                         self.generateText("stdout"))
    return
    self.failUnlessEqual(logs['log2'].getText(),
                         self.generateText("log2"))
    self.failUnlessEqual(logs['log3'].getText(),
                         self.generateText("log3"))
