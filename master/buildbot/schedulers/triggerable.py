from twisted.internet import reactor, defer
from buildbot.schedulers import base
from buildbot.process.properties import Properties

class Triggerable(base.BaseScheduler):
    """This scheduler doesn't do anything until it is triggered by a Trigger
    step in a factory. In general, that step will not complete until all of
    the builds that I fire have finished.
    """

    compare_attrs = ('name', 'builderNames', 'properties')
    def __init__(self, name, builderNames, properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        self._waiters = {}
        self.reason = "Triggerable(%s)" % name

    def trigger(self, ss, set_props=None):
        """Trigger this scheduler. Returns a deferred that will fire when the
        buildset is finished.
        """

        # properties for this buildset are composed of our own properties,
        # potentially overridden by anything from the triggering build
        props = Properties()
        props.updateFromProperties(self.properties)
        if set_props:
            props.updateFromProperties(set_props)

        d = self.parent.db.runInteraction(self._trigger, ss, props)
        # this returns a Deferred that fires when the buildset is complete,
        # with the buildset results (SUCCESS or FAILURE). This Deferred is
        # not persistent: if the master is bounced, the "upstream" build (the
        # one which used steps.trigger.Trigger) will disappear anyways.
        def _done(res):
            return res[0] # chain the Deferred
        d.addCallback(_done)
        return d

    def _trigger(self, t, ss, props):
        db = self.parent.db
        ssid = db.get_sourcestampid(ss, t)
        bsid = self.create_buildset(ssid, self.reason, t, props)
        self._waiters[bsid] = d = defer.Deferred()
        db.scheduler_subscribe_to_buildset(self.schedulerid, bsid, t)
        reactor.callFromThread(self.parent.master.triggerSlaveManager)
        return (d,) # apparently you can't return Deferreds from runInteraction

    def run(self):
        # this exists just to notify triggerers that the builds they
        # triggered are now done, i.e. if buildbot.steps.trigger.Trigger is
        # called with waitForFinish=True.
        d = self.parent.db.runInteraction(self._run)
        return d
    def _run(self, t):
        db = self.parent.db
        res = db.scheduler_get_subscribed_buildsets(self.schedulerid, t)
        # this returns bsid,ssid,results for all of our active subscriptions
        for (bsid,ssid,complete,results) in res:
            if complete:
                d = self._waiters.pop(bsid, None)
                if d:
                    reactor.callFromThread(d.callback, results)
                db.scheduler_unsubscribe_buildset(self.schedulerid, bsid, t)
        return None
