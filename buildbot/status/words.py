
# code to deliver build status through twisted.words (instant messaging
# protocols: irc, etc)

import re, shlex

from zope.interface import Interface, implements
from twisted.internet import protocol, reactor
from twisted.words.protocols import irc
from twisted.python import log, failure
from twisted.application import internet

from buildbot import interfaces, util
from buildbot import version
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest
from buildbot.status import base
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.scripts.runner import ForceOptions

from string import join, capitalize, lower

class UsageError(ValueError):
    def __init__(self, string = "Invalid usage", *more):
        ValueError.__init__(self, string, *more)

class IrcBuildRequest:
    hasStarted = False
    timer = None

    def __init__(self, parent):
        self.parent = parent
        self.timer = reactor.callLater(5, self.soon)

    def soon(self):
        del self.timer
        if not self.hasStarted:
            self.parent.send("The build has been queued, I'll give a shout"
                             " when it starts")

    def started(self, c):
        self.hasStarted = True
        if self.timer:
            self.timer.cancel()
            del self.timer
        s = c.getStatus()
        eta = s.getETA()
        response = "build #%d forced" % s.getNumber()
        if eta is not None:
            response = "build forced [ETA %s]" % self.parent.convertTime(eta)
        self.parent.send(response)
        self.parent.send("I'll give a shout when the build finishes")
        d = s.waitUntilFinished()
        d.addCallback(self.parent.watchedBuildFinished)

class Contact:
    """I hold the state for a single user's interaction with the buildbot.

    This base class provides all the basic behavior (the queries and
    responses). Subclasses for each channel type (IRC, different IM
    protocols) are expected to provide the lower-level send/receive methods.

    There will be one instance of me for each user who interacts personally
    with the buildbot. There will be an additional instance for each
    'broadcast contact' (chat rooms, IRC channels as a whole).
    """

    def __init__(self, channel):
        self.channel = channel
        self.notify_events = {}
        self.subscribed = 0
        self.add_notification_events(channel.notify_events)

    silly = {
        "What happen ?": "Somebody set up us the bomb.",
        "It's You !!": ["How are you gentlemen !!",
                        "All your base are belong to us.",
                        "You are on the way to destruction."],
        "What you say !!": ["You have no chance to survive make your time.",
                            "HA HA HA HA ...."],
        }

    def getCommandMethod(self, command):
        meth = getattr(self, 'command_' + command.upper(), None)
        return meth

    def getBuilder(self, which):
        try:
            b = self.channel.status.getBuilder(which)
        except KeyError:
            raise UsageError, "no such builder '%s'" % which
        return b

    def getControl(self, which):
        if not self.channel.control:
            raise UsageError("builder control is not enabled")
        try:
            bc = self.channel.control.getBuilder(which)
        except KeyError:
            raise UsageError("no such builder '%s'" % which)
        return bc

    def getAllBuilders(self):
        """
        @rtype: list of L{buildbot.process.builder.Builder}
        """
        names = self.channel.status.getBuilderNames(categories=self.channel.categories)
        names.sort()
        builders = [self.channel.status.getBuilder(n) for n in names]
        return builders

    def convertTime(self, seconds):
        if seconds < 60:
            return "%d seconds" % seconds
        minutes = int(seconds / 60)
        seconds = seconds - 60*minutes
        if minutes < 60:
            return "%dm%02ds" % (minutes, seconds)
        hours = int(minutes / 60)
        minutes = minutes - 60*hours
        return "%dh%02dm%02ds" % (hours, minutes, seconds)

    def doSilly(self, message):
        response = self.silly[message]
        if type(response) != type([]):
            response = [response]
        when = 0.5
        for r in response:
            reactor.callLater(when, self.send, r)
            when += 2.5

    def command_HELLO(self, args, who):
        self.send("yes?")

    def command_VERSION(self, args, who):
        self.send("buildbot-%s at your service" % version)

    def command_LIST(self, args, who):
        args = shlex.split(args)
        if len(args) == 0:
            raise UsageError, "try 'list builders'"
        if args[0] == 'builders':
            builders = self.getAllBuilders()
            str = "Configured builders: "
            for b in builders:
                str += b.name
                state = b.getState()[0]
                if state == 'offline':
                    str += "[offline]"
                str += " "
            str.rstrip()
            self.send(str)
            return
    command_LIST.usage = "list builders - List configured builders"

    def command_STATUS(self, args, who):
        args = shlex.split(args)
        if len(args) == 0:
            which = "all"
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError, "try 'status <builder>'"
        if which == "all":
            builders = self.getAllBuilders()
            for b in builders:
                self.emit_status(b.name)
            return
        self.emit_status(which)
    command_STATUS.usage = "status [<which>] - List status of a builder (or all builders)"

    def validate_notification_event(self, event):
        if not re.compile("^(started|finished|success|failure|exception|warnings|(success|warnings|exception|failure)To(Failure|Success|Warnings|Exception))$").match(event):
            raise UsageError("try 'notify on|off <EVENT>'")

    def list_notified_events(self):
        self.send( "The following events are being notified: %r" % self.notify_events.keys() )

    def notify_for(self, *events):
        for event in events:
            if self.notify_events.has_key(event):
                return 1
        return 0

    def subscribe_to_build_events(self):
        self.channel.status.subscribe(self)
        self.subscribed = 1

    def unsubscribe_from_build_events(self):
        self.channel.status.unsubscribe(self)
        self.subscribed = 0

    def add_notification_events(self, events):
        for event in events:
            self.validate_notification_event(event)
            self.notify_events[event] = 1

            if not self.subscribed:
                self.subscribe_to_build_events()

    def remove_notification_events(self, events):
        for event in events:
            self.validate_notification_event(event)
            del self.notify_events[event]

            if len(self.notify_events) == 0 and self.subscribed:
                self.unsubscribe_from_build_events()

    def remove_all_notification_events(self):
        self.notify_events = {}

        if self.subscribed:
            self.unsubscribe_from_build_events()

    def command_NOTIFY(self, args, who):
        args = shlex.split(args)

        if not args:
            raise UsageError("try 'notify on|off|list <EVENT>'")
        action = args.pop(0)
        events = args

        if action == "on":
            if not events: events = ('started','finished')
            self.add_notification_events(events)

            self.list_notified_events()

        elif action == "off":
            if events:
                self.remove_notification_events(events)
            else:
                self.remove_all_notification_events()

            self.list_notified_events()

        elif action == "list":
            self.list_notified_events()
            return

        else:
            raise UsageError("try 'notify on|off <EVENT>'")

    command_NOTIFY.usage = "notify on|off|list [<EVENT>] ... - Notify me about build events.  event should be one or more of: 'started', 'finished', 'failure', 'success', 'exception' or 'xToY' (where x and Y are one of success, warnings, failure, exception, but Y is capitalized)"

    def command_WATCH(self, args, who):
        args = shlex.split(args)
        if len(args) != 1:
            raise UsageError("try 'watch <builder>'")
        which = args[0]
        b = self.getBuilder(which)
        builds = b.getCurrentBuilds()
        if not builds:
            self.send("there are no builds currently running")
            return
        for build in builds:
            assert not build.isFinished()
            d = build.waitUntilFinished()
            d.addCallback(self.watchedBuildFinished)
            r = "watching build %s #%d until it finishes" \
                % (which, build.getNumber())
            eta = build.getETA()
            if eta is not None:
                r += " [%s]" % self.convertTime(eta)
            r += ".."
            self.send(r)
    command_WATCH.usage = "watch <which> - announce the completion of an active build"

    def buildsetSubmitted(self, buildset):
        log.msg('[Contact] Buildset %s added' % (buildset))

    def builderAdded(self, builderName, builder):
        log.msg('[Contact] Builder %s added' % (builder))
        builder.subscribe(self)

    def builderChangedState(self, builderName, state):
        log.msg('[Contact] Builder %s changed state to %s' % (builderName, state))

    def requestSubmitted(self, brstatus):
        log.msg('[Contact] BuildRequest for %s submitted to Builder %s' %
            (brstatus.getSourceStamp(), brstatus.builderName))

    def requestCancelled(self, brstatus):
        # nothing happens with this notification right now
        pass

    def builderRemoved(self, builderName):
        log.msg('[Contact] Builder %s removed' % (builderName))

    def buildStarted(self, builderName, build):
        builder = build.getBuilder()
        log.msg('[Contact] Builder %r in category %s started' % (builder, builder.category))

        # only notify about builders we are interested in

        if (self.channel.categories != None and
           builder.category not in self.channel.categories):
            log.msg('Not notifying for a build in the wrong category')
            return

        if not self.notify_for('started'):
            log.msg('Not notifying for a build when started-notification disabled')
            return

        r = "build #%d of %s started" % \
           (build.getNumber(),
             builder.getName())

        r += " including [" + ", ".join(map(lambda c: repr(c.revision), build.getChanges())) + "]"

        self.send(r)

    results_descriptions = {
        SUCCESS: "Success",
        WARNINGS: "Warnings",
        FAILURE: "Failure",
        EXCEPTION: "Exception",
        }

    def buildFinished(self, builderName, build, results):
        builder = build.getBuilder()

        # only notify about builders we are interested in
        log.msg('[Contact] builder %r in category %s finished' % (builder, builder.category))

        if (self.channel.categories != None and
            builder.category not in self.channel.categories):
            return

        if not self.notify_for_finished(build):
            return

        r = "build #%d of %s is complete: %s" % \
            (build.getNumber(),
             builder.getName(),
             self.results_descriptions.get(build.getResults(), "??"))
        r += " [%s]" % " ".join(build.getText())
        buildurl = self.channel.status.getURLForThing(build)
        if buildurl:
            r += "  Build details are at %s" % buildurl

        if self.channel.showBlameList and build.getResults() != SUCCESS and len(build.changes) != 0:
            r += '  blamelist: ' + ', '.join([c.who for c in build.changes])

        self.send(r)

    def notify_for_finished(self, build):
        results = build.getResults()

        if self.notify_for('finished'):
            return True

        if self.notify_for(lower(self.results_descriptions.get(results))):
            return True

        prevBuild = build.getPreviousBuild()
        if prevBuild:
            prevResult = prevBuild.getResults()

            required_notification_control_string = join((lower(self.results_descriptions.get(prevResult)), \
                                                             'To', \
                                                             capitalize(self.results_descriptions.get(results))), \
                                                            '')

            if (self.notify_for(required_notification_control_string)):
                return True

        return False

    def watchedBuildFinished(self, b):

        # only notify about builders we are interested in
        builder = b.getBuilder()
        log.msg('builder %r in category %s finished' % (builder,
                                                        builder.category))
        if (self.channel.categories != None and
            builder.category not in self.channel.categories):
            return

        r = "Hey! build %s #%d is complete: %s" % \
            (b.getBuilder().getName(),
             b.getNumber(),
             self.results_descriptions.get(b.getResults(), "??"))
        r += " [%s]" % " ".join(b.getText())
        self.send(r)
        buildurl = self.channel.status.getURLForThing(b)
        if buildurl:
            self.send("Build details are at %s" % buildurl)

    def command_FORCE(self, args, who):
        args = shlex.split(args) # TODO: this requires python2.3 or newer
        if not args:
            raise UsageError("try 'force build WHICH <REASON>'")
        what = args.pop(0)
        if what != "build":
            raise UsageError("try 'force build WHICH <REASON>'")
        opts = ForceOptions()
        opts.parseOptions(args)

        which = opts['builder']
        branch = opts['branch']
        revision = opts['revision']
        reason = opts['reason']

        if which is None:
            raise UsageError("you must provide a Builder, "
                             "try 'force build WHICH <REASON>'")

        # keep weird stuff out of the branch and revision strings. TODO:
        # centralize this somewhere.
        if branch and not re.match(r'^[\w\.\-\/]*$', branch):
            log.msg("bad branch '%s'" % branch)
            self.send("sorry, bad branch '%s'" % branch)
            return
        if revision and not re.match(r'^[\w\.\-\/]*$', revision):
            log.msg("bad revision '%s'" % revision)
            self.send("sorry, bad revision '%s'" % revision)
            return

        bc = self.getControl(which)

        r = "forced: by %s: %s" % (self.describeUser(who), reason)
        # TODO: maybe give certain users the ability to request builds of
        # certain branches
        s = SourceStamp(branch=branch, revision=revision)
        req = BuildRequest(r, s, which)
        try:
            bc.requestBuildSoon(req)
        except interfaces.NoSlaveError:
            self.send("sorry, I can't force a build: all slaves are offline")
            return
        ireq = IrcBuildRequest(self)
        req.subscribe(ireq.started)


    command_FORCE.usage = "force build <which> <reason> - Force a build"

    def command_STOP(self, args, who):
        args = shlex.split(args)
        if len(args) < 3 or args[0] != 'build':
            raise UsageError, "try 'stop build WHICH <REASON>'"
        which = args[1]
        reason = args[2]

        buildercontrol = self.getControl(which)

        r = "stopped: by %s: %s" % (self.describeUser(who), reason)

        # find an in-progress build
        builderstatus = self.getBuilder(which)
        builds = builderstatus.getCurrentBuilds()
        if not builds:
            self.send("sorry, no build is currently running")
            return
        for build in builds:
            num = build.getNumber()

            # obtain the BuildControl object
            buildcontrol = buildercontrol.getBuild(num)

            # make it stop
            buildcontrol.stopBuild(r)

            self.send("build %d interrupted" % num)

    command_STOP.usage = "stop build <which> <reason> - Stop a running build"

    def emit_status(self, which):
        b = self.getBuilder(which)
        str = "%s: " % which
        state, builds = b.getState()
        str += state
        if state == "idle":
            last = b.getLastFinishedBuild()
            if last:
                start,finished = last.getTimes()
                str += ", last build %s ago: %s" % \
                        (self.convertTime(int(util.now() - finished)), " ".join(last.getText()))
        if state == "building":
            t = []
            for build in builds:
                step = build.getCurrentStep()
                if step:
                    s = "(%s)" % " ".join(step.getText())
                else:
                    s = "(no current step)"
                ETA = build.getETA()
                if ETA is not None:
                    s += " [ETA %s]" % self.convertTime(ETA)
                t.append(s)
            str += ", ".join(t)
        self.send(str)

    def emit_last(self, which):
        last = self.getBuilder(which).getLastFinishedBuild()
        if not last:
            str = "(no builds run since last restart)"
        else:
            start,finish = last.getTimes()
            str = "%s ago: " % (self.convertTime(int(util.now() - finish)))
            str += " ".join(last.getText())
        self.send("last build [%s]: %s" % (which, str))

    def command_LAST(self, args, who):
        args = shlex.split(args)
        if len(args) == 0:
            which = "all"
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError, "try 'last <builder>'"
        if which == "all":
            builders = self.getAllBuilders()
            for b in builders:
                self.emit_last(b.name)
            return
        self.emit_last(which)
    command_LAST.usage = "last <which> - list last build status for builder <which>"

    def build_commands(self):
        commands = []
        for k in dir(self):
            if k.startswith('command_'):
                commands.append(k[8:].lower())
        commands.sort()
        return commands

    def command_HELP(self, args, who):
        args = shlex.split(args)
        if len(args) == 0:
            self.send("Get help on what? (try 'help <foo>', or 'commands' for a command list)")
            return
        command = args[0]
        meth = self.getCommandMethod(command)
        if not meth:
            raise UsageError, "no such command '%s'" % command
        usage = getattr(meth, 'usage', None)
        if usage:
            self.send("Usage: %s" % usage)
        else:
            self.send("No usage info for '%s'" % command)
    command_HELP.usage = "help <command> - Give help for <command>"

    def command_SOURCE(self, args, who):
        banner = "My source can be found at http://buildbot.net/"
        self.send(banner)

    def command_COMMANDS(self, args, who):
        commands = self.build_commands()
        str = "buildbot commands: " + ", ".join(commands)
        self.send(str)
    command_COMMANDS.usage = "commands - List available commands"

    def command_DESTROY(self, args, who):
        self.act("readies phasers")

    def command_DANCE(self, args, who):
        reactor.callLater(1.0, self.send, "0-<")
        reactor.callLater(3.0, self.send, "0-/")
        reactor.callLater(3.5, self.send, "0-\\")

    def command_EXCITED(self, args, who):
        # like 'buildbot: destroy the sun!'
        self.send("What you say!")

    def handleAction(self, data, user):
        # this is sent when somebody performs an action that mentions the
        # buildbot (like '/me kicks buildbot'). 'user' is the name/nick/id of
        # the person who performed the action, so if their action provokes a
        # response, they can be named.
        if not data.endswith("s buildbot"):
            return
        words = data.split()
        verb = words[-2]
        timeout = 4
        if verb == "kicks":
            response = "%s back" % verb
            timeout = 1
        else:
            response = "%s %s too" % (verb, user)
        reactor.callLater(timeout, self.act, response)

class IRCContact(Contact):
    # this is the IRC-specific subclass of Contact

    def __init__(self, channel, dest):
        Contact.__init__(self, channel)
        # when people send us public messages ("buildbot: command"),
        # self.dest is the name of the channel ("#twisted"). When they send
        # us private messages (/msg buildbot command), self.dest is their
        # username.
        self.dest = dest

    def describeUser(self, user):
        if self.dest[0] == '#':
            return "IRC user <%s> on channel %s" % (user, self.dest)
        return "IRC user <%s> (privmsg)" % user

    # userJoined(self, user, channel)

    def send(self, message):
        self.channel.msgOrNotice(self.dest, message.encode("ascii", "replace"))

    def act(self, action):
        self.channel.me(self.dest, action.encode("ascii", "replace"))

    def command_JOIN(self, args, who):
        args = shlex.split(args)
        to_join = args[0]
        self.channel.join(to_join)
        self.send("Joined %s" % to_join)
    command_JOIN.usage = "join channel - Join another channel"

    def command_LEAVE(self, args, who):
        args = shlex.split(args)
        to_leave = args[0]
        self.send("Buildbot has been told to leave %s" % to_leave)
        self.channel.part(to_leave)
    command_LEAVE.usage = "leave channel - Leave a channel"


    def handleMessage(self, message, who):
        # a message has arrived from 'who'. For broadcast contacts (i.e. when
        # people do an irc 'buildbot: command'), this will be a string
        # describing the sender of the message in some useful-to-log way, and
        # a single Contact may see messages from a variety of users. For
        # unicast contacts (i.e. when people do an irc '/msg buildbot
        # command'), a single Contact will only ever see messages from a
        # single user.
        message = message.lstrip()
        if self.silly.has_key(message):
            return self.doSilly(message)

        parts = message.split(' ', 1)
        if len(parts) == 1:
            parts = parts + ['']
        cmd, args = parts
        log.msg("irc command", cmd)

        meth = self.getCommandMethod(cmd)
        if not meth and message[-1] == '!':
            meth = self.command_EXCITED

        error = None
        try:
            if meth:
                meth(args.strip(), who)
        except UsageError, e:
            self.send(str(e))
        except:
            f = failure.Failure()
            log.err(f)
            error = "Something bad happened (see logs): %s" % f.type

        if error:
            try:
                self.send(error)
            except:
                log.err()

        #self.say(channel, "count %d" % self.counter)
        self.channel.counter += 1

class IChannel(Interface):
    """I represent the buildbot's presence in a particular IM scheme.

    This provides the connection to the IRC server, or represents the
    buildbot's account with an IM service. Each Channel will have zero or
    more Contacts associated with it.
    """

class IrcStatusBot(irc.IRCClient):
    """I represent the buildbot to an IRC server.
    """
    implements(IChannel)
    contactClass = IRCContact

    def __init__(self, nickname, password, channels, status, categories, notify_events, noticeOnChannel = False, showBlameList = False):
        """
        @type  nickname: string
        @param nickname: the nickname by which this bot should be known
        @type  password: string
        @param password: the password to use for identifying with Nickserv
        @type  channels: list of strings
        @param channels: the bot will maintain a presence in these channels
        @type  status: L{buildbot.status.builder.Status}
        @param status: the build master's Status object, through which the
                       bot retrieves all status information
        """
        self.nickname = nickname
        self.channels = channels
        self.password = password
        self.status = status
        self.categories = categories
        self.notify_events = notify_events
        self.counter = 0
        self.hasQuit = 0
        self.contacts = {}
        self.noticeOnChannel = noticeOnChannel
        self.showBlameList = showBlameList

    def msgOrNotice(self, dest, message):
        if self.noticeOnChannel and dest[0] == '#':
            self.notice(dest, message)
        else:
            self.msg(dest, message)

    def addContact(self, name, contact):
        self.contacts[name] = contact

    def getContact(self, name):
        if name in self.contacts:
            return self.contacts[name]
        new_contact = self.contactClass(self, name)
        self.contacts[name] = new_contact
        return new_contact

    def deleteContact(self, contact):
        name = contact.getName()
        if name in self.contacts:
            assert self.contacts[name] == contact
            del self.contacts[name]

    def log(self, msg):
        log.msg("%s: %s" % (self, msg))


    # the following irc.IRCClient methods are called when we have input

    def privmsg(self, user, channel, message):
        user = user.split('!', 1)[0] # rest is ~user@hostname
        # channel is '#twisted' or 'buildbot' (for private messages)
        channel = channel.lower()
        #print "privmsg:", user, channel, message
        if channel == self.nickname:
            # private message
            contact = self.getContact(user)
            contact.handleMessage(message, user)
            return
        # else it's a broadcast message, maybe for us, maybe not. 'channel'
        # is '#twisted' or the like.
        contact = self.getContact(channel)
        if message.startswith("%s:" % self.nickname) or message.startswith("%s," % self.nickname):
            message = message[len("%s:" % self.nickname):]
            contact.handleMessage(message, user)
        # to track users comings and goings, add code here

    def action(self, user, channel, data):
        #log.msg("action: %s,%s,%s" % (user, channel, data))
        user = user.split('!', 1)[0] # rest is ~user@hostname
        # somebody did an action (/me actions) in the broadcast channel
        contact = self.getContact(channel)
        if "buildbot" in data:
            contact.handleAction(data, user)



    def signedOn(self):
        if self.password:
            self.msg("Nickserv", "IDENTIFY " + self.password)
        for c in self.channels:
            self.join(c)

    def joined(self, channel):
        self.log("I have joined %s" % (channel,))
        # trigger contact contructor, which in turn subscribes to notify events
        self.getContact(channel)

    def left(self, channel):
        self.log("I have left %s" % (channel,))
    def kickedFrom(self, channel, kicker, message):
        self.log("I have been kicked from %s by %s: %s" % (channel,
                                                          kicker,
                                                          message))

    # we can using the following irc.IRCClient methods to send output. Most
    # of these are used by the IRCContact class.
    #
    # self.say(channel, message) # broadcast
    # self.msg(user, message) # unicast
    # self.me(channel, action) # send action
    # self.away(message='')
    # self.quit(message='')

class ThrottledClientFactory(protocol.ClientFactory):
    lostDelay = 2
    failedDelay = 60
    def clientConnectionLost(self, connector, reason):
        reactor.callLater(self.lostDelay, connector.connect)
    def clientConnectionFailed(self, connector, reason):
        reactor.callLater(self.failedDelay, connector.connect)

class IrcStatusFactory(ThrottledClientFactory):
    protocol = IrcStatusBot

    status = None
    control = None
    shuttingDown = False
    p = None

    def __init__(self, nickname, password, channels, categories, notify_events, noticeOnChannel = False, showBlameList = False):
        #ThrottledClientFactory.__init__(self) # doesn't exist
        self.status = None
        self.nickname = nickname
        self.password = password
        self.channels = channels
        self.categories = categories
        self.notify_events = notify_events
        self.noticeOnChannel = noticeOnChannel
        self.showBlameList = showBlameList

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['p']
        return d

    def shutdown(self):
        self.shuttingDown = True
        if self.p:
            self.p.quit("buildmaster reconfigured: bot disconnecting")

    def buildProtocol(self, address):
        p = self.protocol(self.nickname, self.password,
                          self.channels, self.status,
                          self.categories, self.notify_events,
                          noticeOnChannel = self.noticeOnChannel,
                          showBlameList = self.showBlameList)
        p.factory = self
        p.status = self.status
        p.control = self.control
        self.p = p
        return p

    # TODO: I think a shutdown that occurs while the connection is being
    # established will make this explode

    def clientConnectionLost(self, connector, reason):
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        ThrottledClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        if self.shuttingDown:
            log.msg("not scheduling reconnection attempt")
            return
        ThrottledClientFactory.clientConnectionFailed(self, connector, reason)


class IRC(base.StatusReceiverMultiService):
    """I am an IRC bot which can be queried for status information. I
    connect to a single IRC server and am known by a single nickname on that
    server, however I can join multiple channels."""

    compare_attrs = ["host", "port", "nick", "password",
                     "channels", "allowForce",
                     "categories"]

    def __init__(self, host, nick, channels, port=6667, allowForce=True,
                 categories=None, password=None, notify_events={},
                 noticeOnChannel = False, showBlameList = True):
        base.StatusReceiverMultiService.__init__(self)

        assert allowForce in (True, False) # TODO: implement others

        # need to stash these so we can detect changes later
        self.host = host
        self.port = port
        self.nick = nick
        self.channels = channels
        self.password = password
        self.allowForce = allowForce
        self.categories = categories
        self.notify_events = notify_events
        log.msg('Notify events %s' % notify_events)
        self.f = IrcStatusFactory(self.nick, self.password,
                                  self.channels, self.categories, self.notify_events,
                                  noticeOnChannel = noticeOnChannel,
                                  showBlameList = showBlameList)
        c = internet.TCPClient(self.host, self.port, self.f)
        c.setServiceParent(self)

    def setServiceParent(self, parent):
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.f.status = parent.getStatus()
        if self.allowForce:
            self.f.control = interfaces.IControl(parent)

    def stopService(self):
        # make sure the factory will stop reconnecting
        self.f.shutdown()
        return base.StatusReceiverMultiService.stopService(self)


## buildbot: list builders
# buildbot: watch quick
#  print notification when current build in 'quick' finishes
## buildbot: status
## buildbot: status full-2.3
##  building, not, % complete, ETA
## buildbot: force build full-2.3 "reason"

