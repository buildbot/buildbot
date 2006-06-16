
import signal
import shutil, os, errno
from twisted.internet import defer, reactor
from twisted.python import log, util

from buildbot import master, interfaces
from buildbot.twcompat import maybeWait
from buildbot.slave import bot
from buildbot.process.base import BuildRequest
from buildbot.sourcestamp import SourceStamp
from buildbot.status import builder

class MyBot(bot.Bot):
    def remote_getSlaveInfo(self):
        return self.parent.info

class MyBuildSlave(bot.BuildSlave):
    botClass = MyBot

def rmtree(d):
    try:
        shutil.rmtree(d, ignore_errors=1)
    except OSError, e:
        # stupid 2.2 appears to ignore ignore_errors
        if e.errno != errno.ENOENT:
            raise

class RunMixin:
    master = None

    def rmtree(self, d):
        rmtree(d)

    def setUp(self):
        self.slaves = {}
        self.rmtree("basedir")
        os.mkdir("basedir")
        self.master = master.BuildMaster("basedir")
        self.status = self.master.getStatus()
        self.control = interfaces.IControl(self.master)

    def connectOneSlave(self, slavename, opts={}):
        port = self.master.slavePort._port.getHost().port
        self.rmtree("slavebase-%s" % slavename)
        os.mkdir("slavebase-%s" % slavename)
        slave = MyBuildSlave("localhost", port, slavename, "sekrit",
                             "slavebase-%s" % slavename,
                             keepalive=0, usePTY=1, debugOpts=opts)
        slave.info = {"admin": "one"}
        self.slaves[slavename] = slave
        slave.startService()

    def connectSlave(self, builders=["dummy"], slavename="bot1",
                     opts={}):
        # connect buildslave 'slavename' and wait for it to connect to all of
        # the given builders
        dl = []
        # initiate call for all of them, before waiting on result,
        # otherwise we might miss some
        for b in builders:
            dl.append(self.master.botmaster.waitUntilBuilderAttached(b))
        d = defer.DeferredList(dl)
        self.connectOneSlave(slavename, opts)
        return d

    def connectSlaves(self, slavenames, builders):
        dl = []
        # initiate call for all of them, before waiting on result,
        # otherwise we might miss some
        for b in builders:
            dl.append(self.master.botmaster.waitUntilBuilderAttached(b))
        d = defer.DeferredList(dl)
        for name in slavenames:
            self.connectOneSlave(name)
        return d

    def connectSlave2(self):
        # this takes over for bot1, so it has to share the slavename
        port = self.master.slavePort._port.getHost().port
        self.rmtree("slavebase-bot2")
        os.mkdir("slavebase-bot2")
        # this uses bot1, really
        slave = MyBuildSlave("localhost", port, "bot1", "sekrit",
                             "slavebase-bot2", keepalive=0, usePTY=1)
        slave.info = {"admin": "two"}
        self.slaves['bot2'] = slave
        slave.startService()

    def connectSlaveFastTimeout(self):
        # this slave has a very fast keepalive timeout
        port = self.master.slavePort._port.getHost().port
        self.rmtree("slavebase-bot1")
        os.mkdir("slavebase-bot1")
        slave = MyBuildSlave("localhost", port, "bot1", "sekrit",
                             "slavebase-bot1", keepalive=2, usePTY=1,
                             keepaliveTimeout=1)
        slave.info = {"admin": "one"}
        self.slaves['bot1'] = slave
        slave.startService()
        d = self.master.botmaster.waitUntilBuilderAttached("dummy")
        return d

    # things to start builds
    def requestBuild(self, builder):
        # returns a Deferred that fires with an IBuildStatus object when the
        # build is finished
        req = BuildRequest("forced build", SourceStamp())
        self.control.getBuilder(builder).requestBuild(req)
        return req.waitUntilFinished()

    def failUnlessBuildSucceeded(self, bs):
        if bs.getResults() != builder.SUCCESS:
            log.msg("failUnlessBuildSucceeded noticed that the build failed")
            self.logBuildResults(bs)
        self.failUnless(bs.getResults() == builder.SUCCESS)
        return bs # useful for chaining

    def logBuildResults(self, bs):
        # emit the build status and the contents of all logs to test.log
        log.msg("logBuildResults starting")
        log.msg(" bs.getResults() == %s" % builder.Results[bs.getResults()])
        log.msg(" bs.isFinished() == %s" % bs.isFinished())
        for s in bs.getSteps():
            for l in s.getLogs():
                log.msg("--- START step %s / log %s ---" % (s.getName(),
                                                            l.getName()))
                if not l.getName().endswith(".html"):
                    log.msg(l.getTextWithHeaders())
                log.msg("--- STOP ---")
        log.msg("logBuildResults finished")

    def tearDown(self):
        log.msg("doing tearDown")
        d = self.shutdownAllSlaves()
        d.addCallback(self._tearDown_1)
        d.addCallback(self._tearDown_2)
        return maybeWait(d)
    def _tearDown_1(self, res):
        if self.master:
            return defer.maybeDeferred(self.master.stopService)
    def _tearDown_2(self, res):
        self.master = None
        log.msg("tearDown done")
        

    # various forms of slave death

    def shutdownAllSlaves(self):
        # the slave has disconnected normally: they SIGINT'ed it, or it shut
        # down willingly. This will kill child processes and give them a
        # chance to finish up. We return a Deferred that will fire when
        # everything is finished shutting down.

        log.msg("doing shutdownAllSlaves")
        dl = []
        for slave in self.slaves.values():
            dl.append(slave.waitUntilDisconnected())
            dl.append(defer.maybeDeferred(slave.stopService))
        d = defer.DeferredList(dl)
        d.addCallback(self._shutdownAllSlavesDone)
        return d
    def _shutdownAllSlavesDone(self, res):
        for name in self.slaves.keys():
            del self.slaves[name]
        return self.master.botmaster.waitUntilBuilderFullyDetached("dummy")

    def shutdownSlave(self, slavename, buildername):
        # this slave has disconnected normally: they SIGINT'ed it, or it shut
        # down willingly. This will kill child processes and give them a
        # chance to finish up. We return a Deferred that will fire when
        # everything is finished shutting down, and the given Builder knows
        # that the slave has gone away.

        s = self.slaves[slavename]
        dl = [self.master.botmaster.waitUntilBuilderDetached(buildername),
              s.waitUntilDisconnected()]
        d = defer.DeferredList(dl)
        d.addCallback(self._shutdownSlave_done, slavename)
        s.stopService()
        return d
    def _shutdownSlave_done(self, res, slavename):
        del self.slaves[slavename]

    def killSlave(self):
        # the slave has died, its host sent a FIN. The .notifyOnDisconnect
        # callbacks will terminate the current step, so the build should be
        # flunked (no further steps should be started).
        self.slaves['bot1'].bf.continueTrying = 0
        bot = self.slaves['bot1'].getServiceNamed("bot")
        broker = bot.builders["dummy"].remote.broker
        broker.transport.loseConnection()
        del self.slaves['bot1']

    def disappearSlave(self, slavename="bot1", buildername="dummy"):
        # the slave's host has vanished off the net, leaving the connection
        # dangling. This will be detected quickly by app-level keepalives or
        # a ping, or slowly by TCP timeouts.

        # simulate this by replacing the slave Broker's .dataReceived method
        # with one that just throws away all data.
        def discard(data):
            pass
        bot = self.slaves[slavename].getServiceNamed("bot")
        broker = bot.builders[buildername].remote.broker
        broker.dataReceived = discard # seal its ears
        broker.transport.write = discard # and take away its voice

    def ghostSlave(self):
        # the slave thinks it has lost the connection, and initiated a
        # reconnect. The master doesn't yet realize it has lost the previous
        # connection, and sees two connections at once.
        raise NotImplementedError


def setupBuildStepStatus(basedir):
    """Return a BuildStep with a suitable BuildStepStatus object, ready to
    use."""
    os.mkdir(basedir)
    botmaster = None
    s0 = builder.Status(botmaster, basedir)
    s1 = s0.builderAdded("buildername", "buildername")
    s2 = builder.BuildStatus(s1, 1)
    s3 = builder.BuildStepStatus(s2)
    s3.setName("foostep")
    s3.started = True
    s3.stepStarted()
    return s3

def findDir():
    # the same directory that holds this script
    return util.sibpath(__file__, ".")

class SignalMixin:
    sigchldHandler = None
    
    def setUpClass(self):
        # make sure SIGCHLD handler is installed, as it should be on
        # reactor.run(). problem is reactor may not have been run when this
        # test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)

    def tearDownClass(self):
        if self.sigchldHandler:
            signal.signal(signal.SIGCHLD, self.sigchldHandler)

# these classes are used to test SlaveCommands in isolation

class FakeSlaveBuilder:
    debug = False
    def __init__(self, usePTY):
        self.updates = []
        self.basedir = findDir()
        self.usePTY = usePTY

    def sendUpdate(self, data):
        if self.debug:
            print "FakeSlaveBuilder.sendUpdate", data
        self.updates.append(data)


