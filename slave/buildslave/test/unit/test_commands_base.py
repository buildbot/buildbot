import sys, re
import pprint
import time

from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.slavebuilder import FakeSlaveBuilder
from buildslave.commands.base import Command, AbandonChain

# set up a fake Command subclass to test the handling in Command.  Think of
# this as testing Command's subclassability.

class DummyCommand(Command):

    def setup(self, args):
        self.setup_done = True
        self.interrupted = False
        self.started = False

    def start(self):
        self.started = True
        self.sendStatus({'rc' : 13})
        self.cmd_deferred = defer.Deferred()
        return self.cmd_deferred

    def interrupt(self):
        self.interrupted = True
        self.finishCommand()

    def finishCommand(self):
        d = self.cmd_deferred
        self.cmd_deferred = None
        d.callback(None)

    def failCommand(self):
        d = self.cmd_deferred
        self.cmd_deferred = None
        d.errback(RuntimeError("forced failure"))

class TestDummyCommand(unittest.TestCase):

    def makeCommand(self, args):
        b = self.builder = FakeSlaveBuilder()
        self.stepid = str(time.time())
        self.cmd = DummyCommand(b, self.stepid, args)
        return self.cmd

    def assertState(self, setup_done, running, started, interrupted, msg=None):
        self.assertEqual(
            {
                'setup_done' : self.cmd.setup_done,
                'running' : self.cmd.running,
                'started' : self.cmd.started,
                'interrupted' : self.cmd.interrupted,
            }, {
                'setup_done' : setup_done,
                'running' : running,
                'started' : started,
                'interrupted' : interrupted,
            }, msg)

    def test_run(self):
        cmd = self.makeCommand({})
        self.assertState(True, False, False, False, "setup called by constructor")

        # start the command
        d = cmd.doStart()
        self.assertState(True, True, True, False, "started and running both set")

        # allow the command to finish and check the result
        cmd.finishCommand()
        def check(_):
            self.assertState(True, False, True, False, "started and not running when done")
        d.addCallback(check)

        def checkresult(_):
            self.assertEqual(self.builder.updates, [ { 'rc' : 13 } ], "updates processed")
        d.addCallback(checkresult)
        return d

    def test_run_failure(self):
        cmd = self.makeCommand({})
        self.assertState(True, False, False, False, "setup called by constructor")

        # start the command
        d = cmd.doStart()
        self.assertState(True, True, True, False, "started and running both set")

        # fail the command with an exception, and check the result
        cmd.failCommand()
        def check(_):
            self.assertState(True, False, True, False, "started and not running when done")
        d.addErrback(check)

        def checkresult(_):
            self.assertEqual(self.builder.updates, [ { 'rc' : 13 } ], "updates processed")
        d.addCallback(checkresult)
        return d

    def test_run_interrupt(self):
        cmd = self.makeCommand({})
        self.assertState(True, False, False, False, "setup called by constructor")

        # start the command
        d = cmd.doStart()
        self.assertState(True, True, True, False, "started and running both set")

        # interrupt the command
        cmd.doInterrupt()
        self.assertTrue(cmd.interrupted)

        def check(_):
            self.assertState(True, False, True, True, "finishes with interrupted set")
        d.addCallback(check)
        return d
