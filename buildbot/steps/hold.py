import datetime
from twisted.python import log
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.status.base import StatusReceiver
from buildbot.process.buildstep import BuildStep
from buildbot.status.words import IRC, IrcStatusFactory, IRCContact, IrcStatusBot
from twisted.internet import reactor

class HeldBuilds(StatusReceiver):
    """Can hold a build when a given build step failed. This gives someone some time
       to repair the build and allow it to continue by potentially unpausing or letting it
       timeout.  These step is best used when IRC module is deployed or some API that can
       interact with hold steps to hold and free them.
       """

    def __init__(self):
        self.held = {}
        self.observers = []

    def getHeldBuilds(self):
        self.clearFinishedBuilds()
        return self.held.values()

    def clearFinishedBuilds(self):
        for id, hold in self.held.items():
            if (hold.build.getStatus().isFinished()):
                self.held.pop(id)

    def subscribe(self, observer):
        """ observer needs to implement this method:
               def buildHeld(self, holdStep)
            to recieve hold build events
        """
        log.msg('Adding observer %s' % str(observer))
        self.observers.append(observer)

    def unsubscribe(self, observer):
        self.observers.remove(observer)

    def add(self, hold_step):
        log.msg('Adding hold step %s' % hold_step.id())
        self.held[hold_step.id()] = hold_step
        hold_step.step_status.subscribe(self)
        for observer in self.observers:
            observer.buildHeld(hold_step)

    def getById(self, id):
        return self.held[id]

    def stepFinished(self, build, step, results):
        log.msg('Removing hold step %s' % hold_step.id())
        self.held.pop(step.id())
        hold_step.step_status.unsubscribe(self)

_held_builds = HeldBuilds()
def heldBuilds():
    """Singleton access to held builds"""
    return _held_builds

class HoldBuild(BuildStep):
    """This will stall a build for a fixed periodic of time. If specified this will only
    hold if a previous step has failed. This can be used to debug a broken build before the 
    system is finishes any other steps, such as teardown steps.  Notifications can be handled
    by subscribing to class returned in global registry: heldBuilds(). One such module that 
    gets held build information is IRC bot that will post messages that a build is being held
    and users and interact with held build."""

    name = 'hold'
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, stepToWatchForFailure=None, timeout=2700, **kwargs):
        """ timeout - default is 45min because you pay same for 1st hour of EC2 so if an average test takes 
                    10 min to start and 5 minutes, that leaves 45 minutes to $ free
            stepToWatchForFailure - is a step in this builder by this name should fail, then this will conditionally hold
                    otherwise this will not hold.  If no step is given, this will ALWAYS hold
        """
        BuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(timeout=timeout, stepToWatchForFailure=stepToWatchForFailure)
        self.defaultTimeout = timeout
        self.timer = None
        self.stepToWatchForFailure = stepToWatchForFailure
        self.doStepIf = self.shouldHold

    def id(self):
        # don't need to add step name because a build can only be held once and so builder name is unique and a lot
        # faster to type
        return self.build.builder.name

    def shouldHold(self, stepInstance):
        if self.stepToWatchForFailure is None:
            return True
        for step in self.build.getStatus().getSteps():
            if step.getName() == self.stepToWatchForFailure:
                return (step.getResults()[0] == FAILURE)
        return False

    def start(self):
        self.hold()
        heldBuilds().add(self)

    def interrupt(self, reason):
        self.stopExistingTimer()
        self.done()

    def stopExistingTimer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
            self.step_status.setText(["delay", "interrupted"])

    def hold(self, timeout=None):
        """Useful for APIs like IRC bot that wish interact with build in progress
        """
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = self.defaultTimeout
        self.stopExistingTimer()
        self.step_status.setText(["delay", "%s secs" % self.timeout])
        log.msg('setting timer')
        self.startTime = datetime.datetime.now()
        self.timer = reactor.callLater(self.timeout, self.done)

    def free(self):
        """Useful for APIs like IRC bot that wish interact with build in progress
        """
        self.stopExistingTimer()
        self.done()

    def done(self):
        self.timer = None
        self.finished(SUCCESS)

def decodeTimeToSeconds(encodedTime):
    units = encodedTime[-1]
    factorTable = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400}
    if (units not in factorTable):
        raise Exception("'%s' does not include a recognized unit of time such as: s, m, h and d. Example: 3h" % encodedTime)
    return factorTable[units] * int(encodedTime[:-1])

class IRCContactWithHold(IRCContact):

    def __init__(self, channel, dest):
        log.msg('Contact created')
        IRCContact.__init__(self, channel, dest)
        # MEMLEAK(?): subscribing but not clear where to unsubscribe
        heldBuilds().subscribe(self);

    def buildHeld(self, heldStep):
        then = heldStep.startTime + datetime.timedelta(seconds=heldStep.timeout)
        heldStep.timeout
        self.send('Holding %s until %s' % (heldStep.id(), then.strftime('%m/%d/%Y %I:%M:%S %p')))

    def command_HOLD(self, args_string, who):
        args = args_string.split(None, 2)
        if len(args) == 0:
            self.listHeldBuilds()
            return
        if len(args) == 2:
            timeout = decodeTimeToSeconds(args[1])
        else:
            timeout = None
        holdStep = self._findHoldStep(args[0])
        if holdStep:
            holdStep.hold(timeout=timeout)
            self.buildHeld(holdStep)

    command_HOLD.usage = "hold [<build step>] [<time to hold e.g. 1h>] ... - Hold, rehold a build or list all held builds. "\
                          "Pass no arguments for a list of all the currently held builds. If you hold an already held system, "\
                          "it will reset the timeout. Examples of time can be an integer immediately followed by d, h, m or s with "\
                          "no space in between."

    def listHeldBuilds(self):
        builds = heldBuilds().getHeldBuilds()
        if len(builds) == 0:
            self.send('No held builds')
        else:
            for hold in builds:
                self.buildHeld(hold)

    def command_FREE(self, hold_step_id, who):
        if len(hold_step_id) > 0:
            holdStep = self._findHoldStep(hold_step_id)
            if holdStep:
                holdStep.free();
                self.send('Releasing held build %s' % hold_step_id)

    command_FREE.usage = "free <build step> ... - Free the build allowing it to go immediately to the next build step."

    def _findHoldStep(self, id):
        holdStep = heldBuilds().getById(id)
        if holdStep is None:
            self.send('Could not find held build step %s' % id)
        return holdStep

class IrcStatusBotWithHold(IrcStatusBot):
    contactClass = IRCContactWithHold

IrcStatusFactory.protocol = IrcStatusBotWithHold

