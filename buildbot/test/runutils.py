
import signal
import shutil, os, errno
from cStringIO import StringIO
from twisted.internet import defer, reactor, protocol
from twisted.python import log, util

from buildbot import master, interfaces
from buildbot.slave import bot
from buildbot.buildslave import BuildSlave
from buildbot.process.builder import Builder
from buildbot.process.base import BuildRequest, Build
from buildbot.process.buildstep import BuildStep
from buildbot.sourcestamp import SourceStamp
from buildbot.status import builder
from buildbot.process.properties import Properties



class _PutEverythingGetter(protocol.ProcessProtocol):
    def __init__(self, deferred, stdin):
        self.deferred = deferred
        self.outBuf = StringIO()
        self.errBuf = StringIO()
        self.outReceived = self.outBuf.write
        self.errReceived = self.errBuf.write
        self.stdin = stdin

    def connectionMade(self):
        if self.stdin is not None:
            self.transport.write(self.stdin)
            self.transport.closeStdin()

    def processEnded(self, reason):
        out = self.outBuf.getvalue()
        err = self.errBuf.getvalue()
        e = reason.value
        code = e.exitCode
        if e.signal:
            self.deferred.errback((out, err, e.signal))
        else:
            self.deferred.callback((out, err, code))

def myGetProcessOutputAndValue(executable, args=(), env={}, path='.',
                               _reactor_ignored=None, stdin=None):
    """Like twisted.internet.utils.getProcessOutputAndValue but takes
    stdin, too."""
    d = defer.Deferred()
    p = _PutEverythingGetter(d, stdin)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path)
    return d


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
                             keepalive=0, usePTY=False, debugOpts=opts)
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

    def connectSlave2(self):
        # this takes over for bot1, so it has to share the slavename
        port = self.master.slavePort._port.getHost().port
        self.rmtree("slavebase-bot2")
        os.mkdir("slavebase-bot2")
        # this uses bot1, really
        slave = MyBuildSlave("localhost", port, "bot1", "sekrit",
                             "slavebase-bot2", keepalive=0, usePTY=False)
        slave.info = {"admin": "two"}
        self.slaves['bot2'] = slave
        slave.startService()

    def connectSlaveFastTimeout(self):
        # this slave has a very fast keepalive timeout
        port = self.master.slavePort._port.getHost().port
        self.rmtree("slavebase-bot1")
        os.mkdir("slavebase-bot1")
        slave = MyBuildSlave("localhost", port, "bot1", "sekrit",
                             "slavebase-bot1", keepalive=2, usePTY=False,
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
        req = BuildRequest("forced build", SourceStamp(), 'test_builder')
        self.control.getBuilder(builder).requestBuild(req)
        return req.waitUntilFinished()

    def failUnlessBuildSucceeded(self, bs):
        if bs.getResults() != builder.SUCCESS:
            log.msg("failUnlessBuildSucceeded noticed that the build failed")
            self.logBuildResults(bs)
        self.failUnlessEqual(bs.getResults(), builder.SUCCESS)
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
        return d
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
            slave.stopService()
            dl.append(slave.waitUntilDisconnected())
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

    def killSlave(self, slavename="bot1", buildername="dummy"):
        # the slave has died, its host sent a FIN. The .notifyOnDisconnect
        # callbacks will terminate the current step, so the build should be
        # flunked (no further steps should be started).
        self.slaves[slavename].bf.continueTrying = 0
        bot = self.slaves[slavename].getServiceNamed("bot")
        broker = bot.builders[buildername].remote.broker
        broker.transport.loseConnection()
        del self.slaves[slavename]

    def disappearSlave(self, slavename="bot1", buildername="dummy",
                       allowReconnect=False):
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
        if not allowReconnect:
            # also discourage it from reconnecting once the connection goes away
            assert self.slaves[slavename].bf.continueTrying
            self.slaves[slavename].bf.continueTrying = False

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

def fake_slaveVersion(command, oldversion=None):
    from buildbot.slave.registry import commandRegistry
    return commandRegistry[command]

class FakeBuildMaster:
    properties = Properties(masterprop="master")

class FakeBotMaster:
    parent = FakeBuildMaster()

def makeBuildStep(basedir, step_class=BuildStep, **kwargs):
    bss = setupBuildStepStatus(basedir)

    ss = SourceStamp()
    setup = {'name': "builder1", "slavename": "bot1",
             'builddir': "builddir", 'slavebuilddir': "slavebuilddir", 'factory': None}
    b0 = Builder(setup, bss.getBuild().getBuilder())
    b0.botmaster = FakeBotMaster()
    br = BuildRequest("reason", ss, 'test_builder')
    b = Build([br])
    b.setBuilder(b0)
    s = step_class(**kwargs)
    s.setBuild(b)
    s.setStepStatus(bss)
    b.build_status = bss.getBuild()
    b.setupProperties()
    s.slaveVersion = fake_slaveVersion
    return s


def findDir():
    # the same directory that holds this script
    return util.sibpath(__file__, ".")

class SignalMixin:
    sigchldHandler = None
    
    def setUpSignalHandler(self):
        # make sure SIGCHLD handler is installed, as it should be on
        # reactor.run(). problem is reactor may not have been run when this
        # test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)

    def tearDownSignalHandler(self):
        if self.sigchldHandler:
            signal.signal(signal.SIGCHLD, self.sigchldHandler)

# these classes are used to test SlaveCommands in isolation

class FakeSlaveBuilder:
    debug = False
    def __init__(self, usePTY, basedir):
        self.updates = []
        self.basedir = basedir
        self.usePTY = usePTY

    def sendUpdate(self, data):
        if self.debug:
            print "FakeSlaveBuilder.sendUpdate", data
        self.updates.append(data)


class SlaveCommandTestBase(SignalMixin):
    usePTY = False

    def setUp(self):
        self.setUpSignalHandler()

    def tearDown(self):
        self.tearDownSignalHandler()

    def setUpBuilder(self, basedir):
        if not os.path.exists(basedir):
            os.mkdir(basedir)
        self.builder = FakeSlaveBuilder(self.usePTY, basedir)

    def startCommand(self, cmdclass, args):
        stepId = 0
        self.cmd = c = cmdclass(self.builder, stepId, args)
        c.running = True
        d = c.doStart()
        return d

    def collectUpdates(self, res=None):
        logs = {}
        for u in self.builder.updates:
            for k in u.keys():
                if k == "log":
                    logname,data = u[k]
                    oldlog = logs.get(("log",logname), "")
                    logs[("log",logname)] = oldlog + data
                elif k == "rc":
                    pass
                else:
                    logs[k] = logs.get(k, "") + u[k]
        return logs

    def findRC(self):
        for u in self.builder.updates:
            if "rc" in u:
                return u["rc"]
        return None

    def printStderr(self):
        for u in self.builder.updates:
            if "stderr" in u:
                print u["stderr"]

# ----------------------------------------

class LocalWrapper:
    # r = pb.Referenceable()
    # w = LocalWrapper(r)
    # now you can do things like w.callRemote()
    def __init__(self, target):
        self.target = target

    def callRemote(self, name, *args, **kwargs):
        # callRemote is not allowed to fire its Deferred in the same turn
        d = defer.Deferred()
        d.addCallback(self._callRemote, *args, **kwargs)
        reactor.callLater(0, d.callback, name)
        return d

    def _callRemote(self, name, *args, **kwargs):
        method = getattr(self.target, "remote_"+name)
        return method(*args, **kwargs)

    def notifyOnDisconnect(self, observer):
        pass
    def dontNotifyOnDisconnect(self, observer):
        pass


class LocalSlaveBuilder(bot.SlaveBuilder):
    """I am object that behaves like a pb.RemoteReference, but in fact I
    invoke methods locally."""
    _arg_filter = None

    def setArgFilter(self, filter):
        self._arg_filter = filter

    def remote_startCommand(self, stepref, stepId, command, args):
        if self._arg_filter:
            args = self._arg_filter(args)
        # stepref should be a RemoteReference to the RemoteCommand
        return bot.SlaveBuilder.remote_startCommand(self,
                                                    LocalWrapper(stepref),
                                                    stepId, command, args)

class StepTester:
    """Utility class to exercise BuildSteps and RemoteCommands, without
    really using a Build or a Bot. No networks are used.

    Use this as follows::

    class MyTest(StepTester, unittest.TestCase):
        def testOne(self):
            self.slavebase = 'testOne.slave'
            self.masterbase = 'testOne.master'
            sb = self.makeSlaveBuilder()
            step = self.makeStep(stepclass, **kwargs)
            d = self.runStep(step)
            d.addCallback(_checkResults)
            return d
    """

    #slavebase = "slavebase"
    slavebuilderbase = "slavebuilderbase"
    #masterbase = "masterbase"

    def makeSlaveBuilder(self):
        os.mkdir(self.slavebase)
        os.mkdir(os.path.join(self.slavebase, self.slavebuilderbase))
        b = bot.Bot(self.slavebase, False)
        b.startService()
        sb = LocalSlaveBuilder("slavebuildername", False)
        sb.setArgFilter(self.filterArgs)
        sb.usePTY = False
        sb.setServiceParent(b)
        sb.setBuilddir(self.slavebuilderbase)
        self.remote = LocalWrapper(sb)
        return sb

    workdir = "build"
    def makeStep(self, factory, **kwargs):
        step = makeBuildStep(self.masterbase, factory, **kwargs)
        step.setBuildSlave(BuildSlave("name", "password"))
        step.setDefaultWorkdir(self.workdir)
        return step

    def runStep(self, step):
        d = defer.maybeDeferred(step.startStep, self.remote)
        return d

    def wrap(self, target):
        return LocalWrapper(target)

    def filterArgs(self, args):
        # this can be overridden
        return args

# ----------------------------------------

_flags = {}

def setTestFlag(flagname, value):
    _flags[flagname] = value

class SetTestFlagStep(BuildStep):
    """
    A special BuildStep to set a named flag; this can be used with the
    TestFlagMixin to monitor what has and has not run in a particular
    configuration.
    """
    def __init__(self, flagname='flag', value=1, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(flagname=flagname, value=value)

        self.flagname = flagname
        self.value = value

    def start(self):
        properties = self.build.getProperties()
        _flags[self.flagname] = properties.render(self.value)
        self.finished(builder.SUCCESS)

class TestFlagMixin:
    def clearFlags(self):
        """
        Set up for a test by clearing all flags; call this from your test
        function.
        """
        _flags.clear()

    def failIfFlagSet(self, flagname, msg=None):
        if not msg: msg = "flag '%s' is set" % flagname
        self.failIf(_flags.has_key(flagname), msg=msg)

    def failIfFlagNotSet(self, flagname, msg=None):
        if not msg: msg = "flag '%s' is not set" % flagname
        self.failUnless(_flags.has_key(flagname), msg=msg)

    def getFlag(self, flagname):
        self.failIfFlagNotSet(flagname, "flag '%s' not set" % flagname)
        return _flags.get(flagname)
