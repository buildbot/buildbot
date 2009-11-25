# Portions copyright Canonical Ltd. 2009

import time
from email.Message import Message
from email.Utils import formatdate
from zope.interface import implements
from twisted.python import log
from twisted.internet import defer, reactor
from twisted.application import service
import twisted.spread.pb

from buildbot.pbutil import NewCredPerspective
from buildbot.status.builder import SlaveStatus
from buildbot.status.mail import MailNotifier
from buildbot.interfaces import IBuildSlave, ILatentBuildSlave
from buildbot.process.properties import Properties

import sys
if sys.version_info[:3] < (2,4,0):
    from sets import Set as set

class AbstractBuildSlave(NewCredPerspective, service.MultiService):
    """This is the master-side representative for a remote buildbot slave.
    There is exactly one for each slave described in the config file (the
    c['slaves'] list). When buildbots connect in (.attach), they get a
    reference to this instance. The BotMaster object is stashed as the
    .botmaster attribute. The BotMaster is also our '.parent' Service.

    I represent a build slave -- a remote machine capable of
    running builds.  I am instantiated by the configuration file, and can be
    subclassed to add extra functionality."""

    implements(IBuildSlave)

    def __init__(self, name, password, max_builds=None,
                 notify_on_missing=[], missing_timeout=3600,
                 properties={}):
        """
        @param name: botname this machine will supply when it connects
        @param password: password this machine will supply when
                         it connects
        @param max_builds: maximum number of simultaneous builds that will
                           be run concurrently on this buildslave (the
                           default is None for no limit)
        @param properties: properties that will be applied to builds run on
                           this slave
        @type properties: dictionary
        """
        service.MultiService.__init__(self)
        self.slavename = name
        self.password = password
        self.botmaster = None # no buildmaster yet
        self.slave_status = SlaveStatus(name)
        self.slave = None # a RemoteReference to the Bot, when connected
        self.slave_commands = None
        self.slavebuilders = {}
        self.max_builds = max_builds

        self.properties = Properties()
        self.properties.update(properties, "BuildSlave")
        self.properties.setProperty("slavename", name, "BuildSlave")

        self.lastMessageReceived = 0
        if isinstance(notify_on_missing, str):
            notify_on_missing = [notify_on_missing]
        self.notify_on_missing = notify_on_missing
        for i in notify_on_missing:
            assert isinstance(i, str)
        self.missing_timeout = missing_timeout
        self.missing_timer = None

    def update(self, new):
        """
        Given a new BuildSlave, configure this one identically.  Because
        BuildSlave objects are remotely referenced, we can't replace them
        without disconnecting the slave, yet there's no reason to do that.
        """
        # the reconfiguration logic should guarantee this:
        assert self.slavename == new.slavename
        assert self.password == new.password
        assert self.__class__ == new.__class__
        self.max_builds = new.max_builds

    def __repr__(self):
        if self.botmaster:
            builders = self.botmaster.getBuildersForSlave(self.slavename)
            return "<%s '%s', current builders: %s>" % \
               (self.__class__.__name__, self.slavename,
                ','.join(map(lambda b: b.name, builders)))
        else:
            return "<%s '%s', (no builders yet)>" % \
                (self.__class__.__name__, self.slavename)

    def setBotmaster(self, botmaster):
        assert not self.botmaster, "BuildSlave already has a botmaster"
        self.botmaster = botmaster
        self.startMissingTimer()

    def stopMissingTimer(self):
        if self.missing_timer:
            self.missing_timer.cancel()
            self.missing_timer = None

    def startMissingTimer(self):
        if self.notify_on_missing and self.missing_timeout and self.parent:
            self.stopMissingTimer() # in case it's already running
            self.missing_timer = reactor.callLater(self.missing_timeout,
                                                   self._missing_timer_fired)

    def _missing_timer_fired(self):
        self.missing_timer = None
        # notify people, but only if we're still in the config
        if not self.parent:
            return

        buildmaster = self.botmaster.parent
        status = buildmaster.getStatus()
        text = "The Buildbot working for '%s'\n" % status.getProjectName()
        text += ("has noticed that the buildslave named %s went away\n" %
                 self.slavename)
        text += "\n"
        text += ("It last disconnected at %s (buildmaster-local time)\n" %
                 time.ctime(time.time() - self.missing_timeout)) # approx
        text += "\n"
        text += "The admin on record (as reported by BUILDSLAVE:info/admin)\n"
        text += "was '%s'.\n" % self.slave_status.getAdmin()
        text += "\n"
        text += "Sincerely,\n"
        text += " The Buildbot\n"
        text += " %s\n" % status.getProjectURL()
        subject = "Buildbot: buildslave %s was lost" % self.slavename
        return self._mail_missing_message(subject, text)


    def updateSlave(self):
        """Called to add or remove builders after the slave has connected.

        @return: a Deferred that indicates when an attached slave has
        accepted the new builders and/or released the old ones."""
        if self.slave:
            return self.sendBuilderList()
        else:
            return defer.succeed(None)

    def updateSlaveStatus(self, buildStarted=None, buildFinished=None):
        if buildStarted:
            self.slave_status.buildStarted(buildStarted)
        if buildFinished:
            self.slave_status.buildFinished(buildFinished)

    def attached(self, bot):
        """This is called when the slave connects.

        @return: a Deferred that fires with a suitable pb.IPerspective to
                 give to the slave (i.e. 'self')"""

        if self.slave:
            # uh-oh, we've got a duplicate slave. The most likely
            # explanation is that the slave is behind a slow link, thinks we
            # went away, and has attempted to reconnect, so we've got two
            # "connections" from the same slave, but the previous one is
            # stale. Give the new one precedence.
            log.msg("duplicate slave %s replacing old one" % self.slavename)

            # just in case we've got two identically-configured slaves,
            # report the IP addresses of both so someone can resolve the
            # squabble
            tport = self.slave.broker.transport
            log.msg("old slave was connected from", tport.getPeer())
            log.msg("new slave is from", bot.broker.transport.getPeer())
            d = self.disconnect()
        else:
            d = defer.succeed(None)
        # now we go through a sequence of calls, gathering information, then
        # tell the Botmaster that it can finally give this slave to all the
        # Builders that care about it.

        # we accumulate slave information in this 'state' dictionary, then
        # set it atomically if we make it far enough through the process
        state = {}

        # Reset graceful shutdown status
        self.slave_status.setGraceful(False)
        # We want to know when the graceful shutdown flag changes
        self.slave_status.addGracefulWatcher(self._gracefulChanged)

        def _log_attachment_on_slave(res):
            d1 = bot.callRemote("print", "attached")
            d1.addErrback(lambda why: None)
            return d1
        d.addCallback(_log_attachment_on_slave)

        def _get_info(res):
            d1 = bot.callRemote("getSlaveInfo")
            def _got_info(info):
                log.msg("Got slaveinfo from '%s'" % self.slavename)
                # TODO: info{} might have other keys
                state["admin"] = info.get("admin")
                state["host"] = info.get("host")
                state["access_uri"] = info.get("access_uri", None)
            def _info_unavailable(why):
                # maybe an old slave, doesn't implement remote_getSlaveInfo
                log.msg("BuildSlave.info_unavailable")
                log.err(why)
            d1.addCallbacks(_got_info, _info_unavailable)
            return d1
        d.addCallback(_get_info)

        def _get_version(res):
            d1 = bot.callRemote("getVersion")
            def _got_version(version):
                state["version"] = version
            def _version_unavailable(why):
                # probably an old slave
                log.msg("BuildSlave.version_unavailable")
                log.err(why)
            d1.addCallbacks(_got_version, _version_unavailable)
        d.addCallback(_get_version)

        def _get_commands(res):
            d1 = bot.callRemote("getCommands")
            def _got_commands(commands):
                state["slave_commands"] = commands
            def _commands_unavailable(why):
                # probably an old slave
                log.msg("BuildSlave._commands_unavailable")
                if why.check(AttributeError):
                    return
                log.err(why)
            d1.addCallbacks(_got_commands, _commands_unavailable)
            return d1
        d.addCallback(_get_commands)

        def _accept_slave(res):
            self.slave_status.setAdmin(state.get("admin"))
            self.slave_status.setHost(state.get("host"))
            self.slave_status.setAccessURI(state.get("access_uri"))
            self.slave_status.setVersion(state.get("version"))
            self.slave_status.setConnected(True)
            self.slave_commands = state.get("slave_commands")
            self.slave = bot
            log.msg("bot attached")
            self.messageReceivedFromSlave()
            self.stopMissingTimer()

            return self.updateSlave()
        d.addCallback(_accept_slave)
        d.addCallback(lambda res: self.botmaster.maybeStartAllBuilds())

        # Finally, the slave gets a reference to this BuildSlave. They
        # receive this later, after we've started using them.
        d.addCallback(lambda res: self)
        return d

    def messageReceivedFromSlave(self):
        now = time.time()
        self.lastMessageReceived = now
        self.slave_status.setLastMessageReceived(now)

    def detached(self, mind):
        self.slave = None
        self.slave_status.removeGracefulWatcher(self._gracefulChanged)
        self.slave_status.setConnected(False)
        log.msg("BuildSlave.detached(%s)" % self.slavename)

    def disconnect(self):
        """Forcibly disconnect the slave.

        This severs the TCP connection and returns a Deferred that will fire
        (with None) when the connection is probably gone.

        If the slave is still alive, they will probably try to reconnect
        again in a moment.

        This is called in two circumstances. The first is when a slave is
        removed from the config file. In this case, when they try to
        reconnect, they will be rejected as an unknown slave. The second is
        when we wind up with two connections for the same slave, in which
        case we disconnect the older connection.
        """

        if not self.slave:
            return defer.succeed(None)
        log.msg("disconnecting old slave %s now" % self.slavename)
        # When this Deferred fires, we'll be ready to accept the new slave
        return self._disconnect(self.slave)

    def _disconnect(self, slave):
        # all kinds of teardown will happen as a result of
        # loseConnection(), but it happens after a reactor iteration or
        # two. Hook the actual disconnect so we can know when it is safe
        # to connect the new slave. We have to wait one additional
        # iteration (with callLater(0)) to make sure the *other*
        # notifyOnDisconnect handlers have had a chance to run.
        d = defer.Deferred()

        # notifyOnDisconnect runs the callback with one argument, the
        # RemoteReference being disconnected.
        def _disconnected(rref):
            reactor.callLater(0, d.callback, None)
        slave.notifyOnDisconnect(_disconnected)
        tport = slave.broker.transport
        # this is the polite way to request that a socket be closed
        tport.loseConnection()
        try:
            # but really we don't want to wait for the transmit queue to
            # drain. The remote end is unlikely to ACK the data, so we'd
            # probably have to wait for a (20-minute) TCP timeout.
            #tport._closeSocket()
            # however, doing _closeSocket (whether before or after
            # loseConnection) somehow prevents the notifyOnDisconnect
            # handlers from being run. Bummer.
            tport.offset = 0
            tport.dataBuffer = ""
        except:
            # however, these hacks are pretty internal, so don't blow up if
            # they fail or are unavailable
            log.msg("failed to accelerate the shutdown process")
            pass
        log.msg("waiting for slave to finish disconnecting")

        return d

    def sendBuilderList(self):
        our_builders = self.botmaster.getBuildersForSlave(self.slavename)
        blist = [(b.name, b.slavebuilddir) for b in our_builders]
        d = self.slave.callRemote("setBuilderList", blist)
        return d

    def perspective_keepalive(self):
        pass

    def addSlaveBuilder(self, sb):
        self.slavebuilders[sb.builder_name] = sb

    def removeSlaveBuilder(self, sb):
        try:
            del self.slavebuilders[sb.builder_name]
        except KeyError:
            pass

    def canStartBuild(self):
        """
        I am called when a build is requested to see if this buildslave
        can start a build.  This function can be used to limit overall
        concurrency on the buildslave.
        """
        # If we're waiting to shutdown gracefully, then we shouldn't
        # accept any new jobs.
        if self.slave_status.getGraceful():
            return False

        if self.max_builds:
            active_builders = [sb for sb in self.slavebuilders.values()
                               if sb.isBusy()]
            if len(active_builders) >= self.max_builds:
                return False
        return True

    def _mail_missing_message(self, subject, text):
        # first, see if we have a MailNotifier we can use. This gives us a
        # fromaddr and a relayhost.
        buildmaster = self.botmaster.parent
        for st in buildmaster.statusTargets:
            if isinstance(st, MailNotifier):
                break
        else:
            # if not, they get a default MailNotifier, which always uses SMTP
            # to localhost and uses a dummy fromaddr of "buildbot".
            log.msg("buildslave-missing msg using default MailNotifier")
            st = MailNotifier("buildbot")
        # now construct the mail

        m = Message()
        m.set_payload(text)
        m['Date'] = formatdate(localtime=True)
        m['Subject'] = subject
        m['From'] = st.fromaddr
        recipients = self.notify_on_missing
        m['To'] = ", ".join(recipients)
        d = st.sendMessage(m, recipients)
        # return the Deferred for testing purposes
        return d

    def _gracefulChanged(self, graceful):
        """This is called when our graceful shutdown setting changes"""
        if graceful:
            active_builders = [sb for sb in self.slavebuilders.values()
                               if sb.isBusy()]
            if len(active_builders) == 0:
                # Shut down!
                self.shutdown()

    def shutdown(self):
        """Shutdown the slave"""
        # Look for a builder with a remote reference to the client side
        # slave.  If we can find one, then call "shutdown" on the remote
        # builder, which will cause the slave buildbot process to exit.
        d = None
        for b in self.slavebuilders.values():
            if b.remote:
                d = b.remote.callRemote("shutdown")
                break

        if d:
            log.msg("Shutting down slave: %s" % self.slavename)
            # The remote shutdown call will not complete successfully since the
            # buildbot process exits almost immediately after getting the
            # shutdown request.
            # Here we look at the reason why the remote call failed, and if
            # it's because the connection was lost, that means the slave
            # shutdown as expected.
            def _errback(why):
                if why.check(twisted.spread.pb.PBConnectionLost):
                    log.msg("Lost connection to %s" % self.slavename)
                else:
                    log.err("Unexpected error when trying to shutdown %s" % self.slavename)
            d.addErrback(_errback)
            return d
        log.err("Couldn't find remote builder to shut down slave")
        return defer.succeed(None)

class BuildSlave(AbstractBuildSlave):

    def sendBuilderList(self):
        d = AbstractBuildSlave.sendBuilderList(self)
        def _sent(slist):
            dl = []
            for name, remote in slist.items():
                # use get() since we might have changed our mind since then
                b = self.botmaster.builders.get(name)
                if b:
                    d1 = b.attached(self, remote, self.slave_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)
        def _set_failed(why):
            log.msg("BuildSlave.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
        d.addCallbacks(_sent, _set_failed)
        return d

    def detached(self, mind):
        AbstractBuildSlave.detached(self, mind)
        self.botmaster.slaveLost(self)
        self.startMissingTimer()

    def buildFinished(self, sb):
        """This is called when a build on this slave is finished."""
        # If we're gracefully shutting down, and we have no more active
        # builders, then it's safe to disconnect
        if self.slave_status.getGraceful():
            active_builders = [sb for sb in self.slavebuilders.values()
                               if sb.isBusy()]
            if len(active_builders) == 0:
                # Shut down!
                return self.shutdown()
        return defer.succeed(None)

class AbstractLatentBuildSlave(AbstractBuildSlave):
    """A build slave that will start up a slave instance when needed.

    To use, subclass and implement start_instance and stop_instance.

    See ec2buildslave.py for a concrete example.  Also see the stub example in
    test/test_slaves.py.
    """

    implements(ILatentBuildSlave)

    substantiated = False
    substantiation_deferred = None
    build_wait_timer = None
    _start_result = _shutdown_callback_handle = None

    def __init__(self, name, password, max_builds=None,
                 notify_on_missing=[], missing_timeout=60*20,
                 build_wait_timeout=60*10,
                 properties={}):
        AbstractBuildSlave.__init__(
            self, name, password, max_builds, notify_on_missing,
            missing_timeout, properties)
        self.building = set()
        self.build_wait_timeout = build_wait_timeout

    def start_instance(self):
        # responsible for starting instance that will try to connect with
        # this master.  Should return deferred.  Problems should use an
        # errback.
        raise NotImplementedError

    def stop_instance(self, fast=False):
        # responsible for shutting down instance.
        raise NotImplementedError

    def substantiate(self, sb):
        if self.substantiated:
            self._clearBuildWaitTimer()
            self._setBuildWaitTimer()
            return defer.succeed(self)
        if self.substantiation_deferred is None:
            if self.parent and not self.missing_timer:
                # start timer.  if timer times out, fail deferred
                self.missing_timer = reactor.callLater(
                    self.missing_timeout,
                    self._substantiation_failed, defer.TimeoutError())
            self.substantiation_deferred = defer.Deferred()
            if self.slave is None:
                self._substantiate() # start up instance
            # else: we're waiting for an old one to detach.  the _substantiate
            # will be done in ``detached`` below.
        return self.substantiation_deferred

    def _substantiate(self):
        # register event trigger
        d = self.start_instance()
        self._shutdown_callback_handle = reactor.addSystemEventTrigger(
            'before', 'shutdown', self._soft_disconnect, fast=True)
        def stash_reply(result):
            self._start_result = result
        def clean_up(failure):
            if self.missing_timer is not None:
                self.missing_timer.cancel()
                self._substantiation_failed(failure)
            if self._shutdown_callback_handle is not None:
                handle = self._shutdown_callback_handle
                del self._shutdown_callback_handle
                reactor.removeSystemEventTrigger(handle)
            return failure
        d.addCallbacks(stash_reply, clean_up)
        return d

    def attached(self, bot):
        if self.substantiation_deferred is None:
            msg = 'Slave %s received connection while not trying to ' \
                    'substantiate.  Disconnecting.' % (self.slavename,)
            log.msg(msg)
            self._disconnect(bot)
            return defer.fail(RuntimeError(msg))
        return AbstractBuildSlave.attached(self, bot)

    def detached(self, mind):
        AbstractBuildSlave.detached(self, mind)
        if self.substantiation_deferred is not None:
            self._substantiate()

    def _substantiation_failed(self, failure):
        d = self.substantiation_deferred
        self.substantiation_deferred = None
        self.missing_timer = None
        d.errback(failure)
        self.insubstantiate()
        # notify people, but only if we're still in the config
        if not self.parent or not self.notify_on_missing:
            return

        buildmaster = self.botmaster.parent
        status = buildmaster.getStatus()
        text = "The Buildbot working for '%s'\n" % status.getProjectName()
        text += ("has noticed that the latent buildslave named %s \n" %
                 self.slavename)
        text += "never substantiated after a request\n"
        text += "\n"
        text += ("The request was made at %s (buildmaster-local time)\n" %
                 time.ctime(time.time() - self.missing_timeout)) # approx
        text += "\n"
        text += "Sincerely,\n"
        text += " The Buildbot\n"
        text += " %s\n" % status.getProjectURL()
        subject = "Buildbot: buildslave %s never substantiated" % self.slavename
        return self._mail_missing_message(subject, text)

    def buildStarted(self, sb):
        assert self.substantiated
        self._clearBuildWaitTimer()
        self.building.add(sb.builder_name)

    def buildFinished(self, sb):
        self.building.remove(sb.builder_name)
        if not self.building:
            self._setBuildWaitTimer()

    def _clearBuildWaitTimer(self):
        if self.build_wait_timer is not None:
            if self.build_wait_timer.active():
                self.build_wait_timer.cancel()
            self.build_wait_timer = None

    def _setBuildWaitTimer(self):
        self._clearBuildWaitTimer()
        self.build_wait_timer = reactor.callLater(
            self.build_wait_timeout, self._soft_disconnect)

    def insubstantiate(self, fast=False):
        self._clearBuildWaitTimer()
        d = self.stop_instance(fast)
        if self._shutdown_callback_handle is not None:
            handle = self._shutdown_callback_handle
            del self._shutdown_callback_handle
            reactor.removeSystemEventTrigger(handle)
        self.substantiated = False
        self.building.clear() # just to be sure
        return d

    def _soft_disconnect(self, fast=False):
        d = AbstractBuildSlave.disconnect(self)
        if self.slave is not None:
            # this could be called when the slave needs to shut down, such as
            # in BotMaster.removeSlave, *or* when a new slave requests a
            # connection when we already have a slave. It's not clear what to
            # do in the second case: this shouldn't happen, and if it
            # does...if it's a latent slave, shutting down will probably kill
            # something we want...but we can't know what the status is. So,
            # here, we just do what should be appropriate for the first case,
            # and put our heads in the sand for the second, at least for now.
            # The best solution to the odd situation is removing it as a
            # possibilty: make the master in charge of connecting to the
            # slave, rather than vice versa. TODO.
            d = defer.DeferredList([d, self.insubstantiate(fast)])
        else:
            if self.substantiation_deferred is not None:
                # unlike the previous block, we don't expect this situation when
                # ``attached`` calls ``disconnect``, only when we get a simple
                # request to "go away".
                self.substantiation_deferred.errback()
                self.substantiation_deferred = None
                if self.missing_timer:
                    self.missing_timer.cancel()
                    self.missing_timer = None
                self.stop_instance()
        return d

    def disconnect(self):
        d = self._soft_disconnect()
        # this removes the slave from all builders.  It won't come back
        # without a restart (or maybe a sighup)
        self.botmaster.slaveLost(self)

    def stopService(self):
        res = defer.maybeDeferred(AbstractBuildSlave.stopService, self)
        if self.slave is not None:
            d = self._soft_disconnect()
            res = defer.DeferredList([res, d])
        return res

    def updateSlave(self):
        """Called to add or remove builders after the slave has connected.

        Also called after botmaster's builders are initially set.

        @return: a Deferred that indicates when an attached slave has
        accepted the new builders and/or released the old ones."""
        for b in self.botmaster.getBuildersForSlave(self.slavename):
            if b.name not in self.slavebuilders:
                b.addLatentSlave(self)
        return AbstractBuildSlave.updateSlave(self)

    def sendBuilderList(self):
        d = AbstractBuildSlave.sendBuilderList(self)
        def _sent(slist):
            dl = []
            for name, remote in slist.items():
                # use get() since we might have changed our mind since then.
                # we're checking on the builder in addition to the
                # slavebuilders out of a bit of paranoia.
                b = self.botmaster.builders.get(name)
                sb = self.slavebuilders.get(name)
                if b and sb:
                    d1 = sb.attached(self, remote, self.slave_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)
        def _set_failed(why):
            log.msg("BuildSlave.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
            if self.substantiation_deferred:
                self.substantiation_deferred.errback()
                self.substantiation_deferred = None
            if self.missing_timer:
                self.missing_timer.cancel()
                self.missing_timer = None
            # TODO: maybe log?  send an email?
            return why
        d.addCallbacks(_sent, _set_failed)
        def _substantiated(res):
            self.substantiated = True
            if self.substantiation_deferred:
                d = self.substantiation_deferred
                del self.substantiation_deferred
                res = self._start_result
                del self._start_result
                d.callback(res)
            # note that the missing_timer is already handled within
            # ``attached``
            if not self.building:
                self._setBuildWaitTimer()
        d.addCallback(_substantiated)
        return d
