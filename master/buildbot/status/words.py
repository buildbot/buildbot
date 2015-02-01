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

import random
import re
import shlex

from string import capitalize
from string import join
from string import lower

from twisted.application import internet
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.python import usage
from twisted.words.protocols import irc
from zope.interface import implements

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot import version
from buildbot.interfaces import IStatusReceiver
from buildbot.process.properties import Properties
from buildbot.sourcestamp import SourceStamp
from buildbot.status import base
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import RETRY
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS

# twisted.internet.ssl requires PyOpenSSL, so be resilient if it's missing
try:
    from twisted.internet import ssl
    have_ssl = True
except ImportError:
    have_ssl = False


def maybeColorize(text, color, useColors):
    irc_colors = [
        'WHITE',
        'BLACK',
        'NAVY_BLUE',
        'GREEN',
        'RED',
        'BROWN',
        'PURPLE',
        'OLIVE',
        'YELLOW',
        'LIME_GREEN',
        'TEAL',
        'AQUA_LIGHT',
        'ROYAL_BLUE',
        'HOT_PINK',
        'DARK_GRAY',
        'LIGHT_GRAY'
    ]

    if useColors:
        return "%c%d%s%c" % (3, irc_colors.index(color), text, 3)
    else:
        return text


class UsageError(ValueError):

    def __init__(self, string="Invalid usage", *more):
        ValueError.__init__(self, string, *more)


class ForceOptions(usage.Options):
    optParameters = [
        ["builder", None, None, "which Builder to start"],
        ["branch", None, None, "which branch to build"],
        ["revision", None, None, "which revision to build"],
        ["reason", None, None, "the reason for starting the build"],
        ["props", None, None,
         "A set of properties made available in the build environment, "
         "format is --properties=prop1=value1,prop2=value2,.. "
         "option can be specified multiple times."],
    ]

    def parseArgs(self, *args):
        args = list(args)
        if len(args) > 0:
            if self['builder'] is not None:
                raise UsageError("--builder provided in two ways")
            self['builder'] = args.pop(0)
        if len(args) > 0:
            if self['reason'] is not None:
                raise UsageError("--reason provided in two ways")
            self['reason'] = " ".join(args)


class IrcBuildRequest:
    hasStarted = False
    timer = None

    def __init__(self, parent, useRevisions=False, useColors=True):
        self.parent = parent
        self.useRevisions = useRevisions
        self.useColors = useColors
        self.timer = reactor.callLater(5, self.soon)

    def soon(self):
        del self.timer
        if not self.hasStarted:
            self.parent.send("The build has been queued, I'll give a shout"
                             " when it starts")

    def started(self, s):
        self.hasStarted = True
        if self.timer:
            self.timer.cancel()
            del self.timer
        eta = s.getETA()
        if self.useRevisions:
            response = "build containing revision(s) [%s] forced" % s.getRevisions()
        else:
            response = "build #%d forced" % s.getNumber()
        if eta is not None:
            response = "build forced [ETA %s]" % self.parent.convertTime(eta)
        self.parent.send(response)
        self.parent.send("I'll give a shout when the build finishes")
        d = s.waitUntilFinished()
        d.addCallback(self.parent.watchedBuildFinished)


class IRCContact(base.StatusReceiver):
    implements(IStatusReceiver)
    """I hold the state for a single user's interaction with the buildbot.

    There will be one instance of me for each user who interacts personally
    with the buildbot. There will be an additional instance for each
    'broadcast contact' (chat rooms, IRC channels as a whole).
    """

    def __init__(self, bot, dest):
        self.bot = bot
        self.master = bot.master
        self.notify_events = {}
        self.subscribed = 0
        self.muted = False
        self.useRevisions = bot.useRevisions
        self.useColors = bot.useColors
        self.reported_builds = []  # tuples (when, buildername, buildnum)
        self.add_notification_events(bot.notify_events)

        # when people send us public messages ("buildbot: command"),
        # self.dest is the name of the channel ("#twisted"). When they send
        # us private messages (/msg buildbot command), self.dest is their
        # username.
        self.dest = dest

    # silliness

    silly = {
        "What happen ?": ["Somebody set up us the bomb."],
        "It's You !!": ["How are you gentlemen !!",
                        "All your base are belong to us.",
                        "You are on the way to destruction."],
        "What you say !!": ["You have no chance to survive make your time.",
                            "HA HA HA HA ...."],
    }

    def doSilly(self, message):
        response = self.silly[message]
        when = 0.5
        for r in response:
            reactor.callLater(when, self.send, r)
            when += 2.5

    def getBuilder(self, which):
        try:
            b = self.bot.status.getBuilder(which)
        except KeyError:
            raise UsageError("no such builder '%s'" % which)
        return b

    def getControl(self, which):
        if not self.bot.control:
            raise UsageError("builder control is not enabled")
        try:
            bc = self.bot.control.getBuilder(which)
        except KeyError:
            raise UsageError("no such builder '%s'" % which)
        return bc

    def getAllBuilders(self):
        """
        @rtype: list of L{buildbot.process.builder.Builder}
        """
        names = sorted(self.bot.status.getBuilderNames(tags=self.bot.tags))
        builders = [self.bot.status.getBuilder(n) for n in names]
        return builders

    def convertTime(self, seconds):
        if seconds < 60:
            return "%d seconds" % seconds
        minutes = int(seconds / 60)
        seconds = seconds - 60 * minutes
        if minutes < 60:
            return "%dm%02ds" % (minutes, seconds)
        hours = int(minutes / 60)
        minutes = minutes - 60 * hours
        return "%dh%02dm%02ds" % (hours, minutes, seconds)

    def reportBuild(self, builder, buildnum):
        """Returns True if this build should be reported for this contact
        (eliminating duplicates), and also records the report for later"""
        for w, b, n in self.reported_builds:
            if b == builder and n == buildnum:
                return False
        self.reported_builds.append([util.now(), builder, buildnum])

        # clean the reported builds
        horizon = util.now() - 60
        while self.reported_builds and self.reported_builds[0][0] < horizon:
            self.reported_builds.pop(0)

        # and return True, since this is a new one
        return True

    def splitArgs(self, args):
        """Returns list of arguments parsed by shlex.split() or
        raise UsageError if failed"""
        try:
            return shlex.split(args)
        except ValueError, e:
            raise UsageError(e)

    def command_HELLO(self, args, who):
        self.send("yes?")

    def command_VERSION(self, args, who):
        self.send("buildbot-%s at your service" % version)

    def command_LIST(self, args, who):
        args = self.splitArgs(args)
        if len(args) == 0:
            raise UsageError("try 'list builders'")
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
        args = self.splitArgs(args)
        if len(args) == 0:
            which = "all"
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError("try 'status <builder>'")
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
        self.send("The following events are being notified: %r" % self.notify_events.keys())

    def notify_for(self, *events):
        for event in events:
            if event in self.notify_events:
                return 1
        return 0

    def subscribe_to_build_events(self):
        self.bot.status.subscribe(self)
        self.subscribed = 1

    def unsubscribe_from_build_events(self):
        self.bot.status.unsubscribe(self)
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
        args = self.splitArgs(args)

        if not args:
            raise UsageError("try 'notify on|off|list <EVENT>'")
        action = args.pop(0)
        events = args

        if action == "on":
            if not events:
                events = ('started', 'finished')
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
        args = self.splitArgs(args)
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
            if self.useRevisions:
                r = "watching build %s containing revision(s) [%s] until it finishes" \
                    % (which, build.getRevisions())
            else:
                r = "watching build %s #%d until it finishes" \
                    % (which, build.getNumber())
            eta = build.getETA()
            if eta is not None:
                r += " [%s]" % self.convertTime(eta)
            r += ".."
            self.send(r)
    command_WATCH.usage = "watch <which> - announce the completion of an active build"

    def builderAdded(self, builderName, builder):
        if (self.bot.tags is not None and
                not builder.matchesAnyTag(self.bot.tags)):
            return

        log.msg('[Contact] Builder %s added' % (builderName))
        builder.subscribe(self)

    def builderRemoved(self, builderName):
        log.msg('[Contact] Builder %s removed' % (builderName))

    def buildStarted(self, builderName, build):
        builder = build.getBuilder()
        log.msg('[Contact] Builder %r with tags %r started' % (builder, builder.getTags()))

        # only notify about builders we are interested in

        if (self.bot.tags is not None and
           not builder.matchesAnyTag(self.bot.tags)):
            log.msg('Not notifying for a build with no matching tag')
            return

        if not self.notify_for('started'):
            return

        if self.useRevisions:
            r = "build containing revision(s) [%s] on %s started" % \
                (build.getRevisions(), builder.getName())
        else:
            # Abbreviate long lists of changes to simply two
            # revisions, and the number of additional changes.
            changes = [str(c.revision) for c in build.getChanges()][:2]
            changes_str = ""

            if len(build.getChanges()) > 0:
                changes_str = "including [%s]" % ', '.join(changes)

                if len(build.getChanges()) > 2:
                    # Append number of truncated changes
                    changes_str += " and %d more" % (len(build.getChanges()) - 2)

            r = "build #%d of %s started" % (
                build.getNumber(),
                builder.getName())

            if changes_str:
                r += " (%s)" % changes_str

        self.send(r)

    results_descriptions = {
        SUCCESS: ("Success", 'GREEN'),
        WARNINGS: ("Warnings", 'YELLOW'),
        FAILURE: ("Failure", 'RED'),
        EXCEPTION: ("Exception", 'PURPLE'),
        RETRY: ("Retry", 'AQUA_LIGHT'),
    }

    def getResultsDescriptionAndColor(self, results):
        return self.results_descriptions.get(results, ("??", 'RED'))

    def buildFinished(self, builderName, build, results):
        builder = build.getBuilder()

        if (self.bot.tags is not None and
                not builder.matchesAnyTag(self.bot.tags)):
            return

        if not self.notify_for_finished(build):
            return

        builder_name = builder.getName()
        buildnum = build.getNumber()
        buildrevs = build.getRevisions()

        results = self.getResultsDescriptionAndColor(build.getResults())
        if self.reportBuild(builder_name, buildnum):
            if self.useRevisions:
                r = "build containing revision(s) [%s] on %s is complete: %s" % \
                    (buildrevs, builder_name, results[0])
            else:
                r = "build #%d of %s is complete: %s" % \
                    (buildnum, builder_name, results[0])

            r += ' [%s]' % maybeColorize(" ".join(build.getText()), results[1], self.useColors)
            buildurl = self.bot.status.getURLForThing(build)
            if buildurl:
                r += "  Build details are at %s" % buildurl

            if self.bot.showBlameList and build.getResults() != SUCCESS and len(build.changes) != 0:
                r += '  blamelist: ' + ', '.join(list(set([c.who for c in build.changes])))

            self.send(r)

    def notify_for_finished(self, build):
        results = build.getResults()

        if self.notify_for('finished'):
            return True

        if self.notify_for(lower(self.results_descriptions.get(results)[0])):
            return True

        prevBuild = build.getPreviousBuild()
        if prevBuild:
            prevResult = prevBuild.getResults()

            required_notification_control_string = join((lower(self.results_descriptions.get(prevResult)[0]),
                                                         'To',
                                                         capitalize(self.results_descriptions.get(results)[0])),
                                                        '')

            if (self.notify_for(required_notification_control_string)):
                return True

        return False

    def watchedBuildFinished(self, b):

        # only notify about builders we are interested in
        builder = b.getBuilder()
        if (self.bot.tags is not None and
                not builder.matchesAnyTag(self.bot.tags)):
            return

        builder_name = builder.getName()
        buildnum = b.getNumber()
        buildrevs = b.getRevisions()

        results = self.getResultsDescriptionAndColor(b.getResults())
        if self.reportBuild(builder_name, buildnum):
            if self.useRevisions:
                r = "Hey! build %s containing revision(s) [%s] is complete: %s" % \
                    (builder_name, buildrevs, results[0])
            else:
                r = "Hey! build %s #%d is complete: %s" % \
                    (builder_name, buildnum, results[0])

            r += ' [%s]' % maybeColorize(" ".join(b.getText()), results[1], self.useColors)
            self.send(r)
            buildurl = self.bot.status.getURLForThing(b)
            if buildurl:
                self.send("Build details are at %s" % buildurl)

    def command_FORCE(self, args, who):
        errReply = "try 'force build [--branch=BRANCH] [--revision=REVISION] [--props=PROP1=VAL1,PROP2=VAL2...]  <WHICH> <REASON>'"
        args = self.splitArgs(args)
        if not args:
            raise UsageError(errReply)
        what = args.pop(0)
        if what != "build":
            raise UsageError(errReply)
        opts = ForceOptions()
        opts.parseOptions(args)

        which = opts['builder']
        branch = opts['branch']
        revision = opts['revision']
        reason = opts['reason']
        props = opts['props']

        if which is None:
            raise UsageError("you must provide a Builder, " + errReply)

        # keep weird stuff out of the branch, revision, and properties args.
        branch_validate = self.master.config.validation['branch']
        revision_validate = self.master.config.validation['revision']
        pname_validate = self.master.config.validation['property_name']
        pval_validate = self.master.config.validation['property_value']
        if branch and not branch_validate.match(branch):
            log.msg("bad branch '%s'" % branch)
            self.send("sorry, bad branch '%s'" % branch)
            return
        if revision and not revision_validate.match(revision):
            log.msg("bad revision '%s'" % revision)
            self.send("sorry, bad revision '%s'" % revision)
            return

        properties = Properties()
        if props:
            # split props into name:value dict
            pdict = {}
            propertylist = props.split(",")
            for i in range(0, len(propertylist)):
                splitproperty = propertylist[i].split("=", 1)
                pdict[splitproperty[0]] = splitproperty[1]

            # set properties
            for prop in pdict:
                pname = prop
                pvalue = pdict[prop]
                if not pname_validate.match(pname) \
                        or not pval_validate.match(pvalue):
                    log.msg("bad property name='%s', value='%s'" % (pname, pvalue))
                    self.send("sorry, bad property name='%s', value='%s'" %
                              (pname, pvalue))
                    return
                properties.setProperty(pname, pvalue, "Force Build IRC")

        bc = self.getControl(which)

        reason = "forced: by %s: %s" % (self.describeUser(who), reason)
        ss = SourceStamp(branch=branch, revision=revision)
        d = bc.submitBuildRequest(ss, reason, props=properties.asDict())

        def subscribe(buildreq):
            ireq = IrcBuildRequest(self, self.useRevisions)
            buildreq.subscribe(ireq.started)
        d.addCallback(subscribe)
        d.addErrback(log.err, "while forcing a build")

    command_FORCE.usage = "force build [--branch=branch] [--revision=revision] [--props=prop1=val1,prop2=val2...] <which> <reason> - Force a build"

    def command_STOP(self, args, who):
        args = self.splitArgs(args)
        if len(args) < 3 or args[0] != 'build':
            raise UsageError("try 'stop build WHICH <REASON>'")
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
            revs = build.getRevisions()

            # obtain the BuildControl object
            buildcontrol = buildercontrol.getBuild(num)

            # make it stop
            buildcontrol.stopBuild(r)

            if self.useRevisions:
                response = "build containing revision(s) [%s] interrupted" % revs
            else:
                response = "build %d interrupted" % num
            self.send(response)

    command_STOP.usage = "stop build <which> <reason> - Stop a running build"

    def emit_status(self, which):
        b = self.getBuilder(which)
        str = "%s: " % which
        state, builds = b.getState()
        str += state
        if state == "idle":
            last = b.getLastFinishedBuild()
            if last:
                start, finished = last.getTimes()
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

    def command_LAST(self, args, who):
        args = self.splitArgs(args)

        if len(args) == 0:
            which = "all"
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError("try 'last <builder>'")

        def emit_last(which):
            last = self.getBuilder(which).getLastFinishedBuild()
            if not last:
                str = "(no builds run since last restart)"
            else:
                start, finish = last.getTimes()
                str = "%s ago: " % (self.convertTime(int(util.now() - finish)))
                str += " ".join(last.getText())
            self.send("last build [%s]: %s" % (which, str))

        if which == "all":
            builders = self.getAllBuilders()
            for b in builders:
                emit_last(b.name)
            return
        emit_last(which)
    command_LAST.usage = "last <which> - list last build status for builder <which>"

    def build_commands(self):
        commands = []
        for k in dir(self):
            if k.startswith('command_'):
                commands.append(k[8:].lower())
        commands.sort()
        return commands

    def describeUser(self, user):
        if self.dest[0] == '#':
            return "IRC user <%s> on channel %s" % (user, self.dest)
        return "IRC user <%s> (privmsg)" % user

    # commands

    def command_MUTE(self, args, who):
        # The order of these is important! ;)
        self.send("Shutting up for now.")
        self.muted = True
    command_MUTE.usage = "mute - suppress all messages until a corresponding 'unmute' is issued"

    def command_UNMUTE(self, args, who):
        if self.muted:
            # The order of these is important! ;)
            self.muted = False
            self.send("I'm baaaaaaaaaaack!")
        else:
            self.send("You hadn't told me to be quiet, but it's the thought that counts, right?")
    command_UNMUTE.usage = "unmute - disable a previous 'mute'"

    def command_HELP(self, args, who):
        args = self.splitArgs(args)
        if len(args) == 0:
            self.send("Get help on what? (try 'help <foo>', 'help <foo> <bar>, "
                      "or 'commands' for a command list)")
            return
        command = args[0]
        meth = self.getCommandMethod(command)
        if not meth:
            raise UsageError("no such command '%s'" % command)
        usage = getattr(meth, 'usage', None)
        if isinstance(usage, dict):
            if len(args) == 1:
                k = None  # command
            elif len(args) == 2:
                k = args[1]  # command arg
            else:
                k = tuple(args[1:])  # command arg subarg ...
            usage = usage.get(k, None)
        if usage:
            self.send("Usage: %s" % usage)
        else:
            self.send("No usage info for " + ' '.join(["'%s'" % arg for arg in args]))
    command_HELP.usage = "help <command> [<arg> [<subarg> ...]] - Give help for <command> or one of it's arguments"

    def command_SOURCE(self, args, who):
        self.send("My source can be found at "
                  "https://github.com/buildbot/buildbot")
    command_SOURCE.usage = "source - the source code for Buildbot"

    def command_COMMANDS(self, args, who):
        commands = self.build_commands()
        str = "buildbot commands: " + ", ".join(commands)
        self.send(str)
    command_COMMANDS.usage = "commands - List available commands"

    def command_DESTROY(self, args, who):
        if self.bot.nickname not in args:
            self.act("readies phasers")

    def command_DANCE(self, args, who):
        reactor.callLater(1.0, self.send, "<(^.^<)")
        reactor.callLater(2.0, self.send, "<(^.^)>")
        reactor.callLater(3.0, self.send, "(>^.^)>")
        reactor.callLater(3.5, self.send, "(7^.^)7")
        reactor.callLater(5.0, self.send, "(>^.^<)")

    def command_SHUTDOWN(self, args, who):
        if args not in ('check', 'start', 'stop', 'now'):
            raise UsageError("try 'shutdown check|start|stop|now'")

        if not self.bot.factory.allowShutdown:
            raise UsageError("shutdown control is not enabled")

        botmaster = self.master.botmaster
        shuttingDown = botmaster.shuttingDown

        if args == 'check':
            if shuttingDown:
                self.send("Status: buildbot is shutting down")
            else:
                self.send("Status: buildbot is running")
        elif args == 'start':
            if shuttingDown:
                self.send("Already started")
            else:
                self.send("Starting clean shutdown")
                botmaster.cleanShutdown()
        elif args == 'stop':
            if not shuttingDown:
                self.send("Nothing to stop")
            else:
                self.send("Stopping clean shutdown")
                botmaster.cancelCleanShutdown()
        elif args == 'now':
            self.send("Stopping buildbot")
            reactor.stop()
    command_SHUTDOWN.usage = {
        None: "shutdown check|start|stop|now - shutdown the buildbot master",
        "check": "shutdown check - check if the buildbot master is running or shutting down",
        "start": "shutdown start - start a clean shutdown",
        "stop": "shutdown cancel - stop the clean shutdown",
        "now": "shutdown now - shutdown immediately without waiting for the builders to finish"}

    # communication with the user

    def send(self, message):
        if not self.muted:
            self.bot.msgOrNotice(self.dest, message.encode("ascii", "replace"))

    def act(self, action):
        if not self.muted:
            self.bot.describe(self.dest, action.encode("ascii", "replace"))

    # main dispatchers for incoming messages

    def getCommandMethod(self, command):
        return getattr(self, 'command_' + command.upper(), None)

    def handleMessage(self, message, who):
        # a message has arrived from 'who'. For broadcast contacts (i.e. when
        # people do an irc 'buildbot: command'), this will be a string
        # describing the sender of the message in some useful-to-log way, and
        # a single Contact may see messages from a variety of users. For
        # unicast contacts (i.e. when people do an irc '/msg buildbot
        # command'), a single Contact will only ever see messages from a
        # single user.
        message = message.lstrip()
        if message in self.silly:
            self.doSilly(message)
            return defer.succeed(None)

        parts = message.split(' ', 1)
        if len(parts) == 1:
            parts = parts + ['']
        cmd, args = parts
        log.msg("irc command", cmd)

        meth = self.getCommandMethod(cmd)
        if not meth and message[-1] == '!':
            self.send("What you say!")
            return defer.succeed(None)

        if meth:
            d = defer.maybeDeferred(meth, args.strip(), who)

            @d.addErrback
            def usageError(f):
                f.trap(UsageError)
                self.send(str(f.value))

            @d.addErrback
            def logErr(f):
                log.err(f)
                self.send("Something bad happened (see logs)")
            d.addErrback(log.err)
            return d
        return defer.succeed(None)

    def handleAction(self, data, user):
        # this is sent when somebody performs an action that mentions the
        # buildbot (like '/me kicks buildbot'). 'user' is the name/nick/id of
        # the person who performed the action, so if their action provokes a
        # response, they can be named.  This is 100% silly.
        if not data.endswith("s " + self.bot.nickname):
            return
        words = data.split()
        verb = words[-2]
        if verb == "kicks":
            response = "%s back" % verb
        else:
            response = "%s %s too" % (verb, user)
        self.act(response)


class IrcStatusBot(irc.IRCClient):

    """I represent the buildbot to an IRC server.
    """
    contactClass = IRCContact

    def __init__(self, nickname, password, channels, pm_to_nicks, status,
                 tags, notify_events, noticeOnChannel=False,
                 useRevisions=False, showBlameList=False, useColors=True):
        self.nickname = nickname
        self.channels = channels
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        self.status = status
        self.master = status.master
        self.tags = tags
        self.notify_events = notify_events
        self.hasQuit = 0
        self.contacts = {}
        self.noticeOnChannel = noticeOnChannel
        self.useColors = useColors
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self._keepAliveCall = task.LoopingCall(lambda: self.ping(self.nickname))

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self._keepAliveCall.start(60)

    def connectionLost(self, reason):
        if self._keepAliveCall.running:
            self._keepAliveCall.stop()
        irc.IRCClient.connectionLost(self, reason)

    def msgOrNotice(self, dest, message):
        if self.noticeOnChannel and dest[0] == '#':
            self.notice(dest, message)
        else:
            self.msg(dest, message)

    def getContact(self, name):
        name = name.lower()  # nicknames and channel names are case insensitive
        if name in self.contacts:
            return self.contacts[name]
        new_contact = self.contactClass(self, name)
        self.contacts[name] = new_contact
        return new_contact

    def log(self, msg):
        log.msg("%s: %s" % (self, msg))

    # the following irc.IRCClient methods are called when we have input
    def privmsg(self, user, channel, message):
        user = user.split('!', 1)[0]  # rest is ~user@hostname
        # channel is '#twisted' or 'buildbot' (for private messages)
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

    def action(self, user, channel, data):
        user = user.split('!', 1)[0]  # rest is ~user@hostname
        # somebody did an action (/me actions) in the broadcast channel
        contact = self.getContact(channel)
        if self.nickname in data:
            contact.handleAction(data, user)

    def signedOn(self):
        if self.password:
            self.msg("Nickserv", "IDENTIFY " + self.password)
        for c in self.channels:
            if isinstance(c, dict):
                channel = c.get('channel', None)
                password = c.get('password', None)
            else:
                channel = c
                password = None
            self.join(channel=channel, key=password)
        for c in self.pm_to_nicks:
            self.getContact(c)

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


class ThrottledClientFactory(protocol.ClientFactory):
    lostDelay = random.randint(1, 5)
    failedDelay = random.randint(45, 60)

    def __init__(self, lostDelay=None, failedDelay=None):
        if lostDelay is not None:
            self.lostDelay = lostDelay
        if failedDelay is not None:
            self.failedDelay = failedDelay

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

    def __init__(self, nickname, password, channels, pm_to_nicks, tags, notify_events,
                 noticeOnChannel=False, useRevisions=False, showBlameList=False,
                 lostDelay=None, failedDelay=None, useColors=True, allowShutdown=False,
                 categories=None  # deprecated, use tags instead
                 ):
        ThrottledClientFactory.__init__(self, lostDelay=lostDelay,
                                        failedDelay=failedDelay)
        self.status = None
        self.nickname = nickname
        self.password = password
        self.channels = channels
        self.pm_to_nicks = pm_to_nicks
        self.tags = tags or categories
        self.notify_events = notify_events
        self.noticeOnChannel = noticeOnChannel
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self.useColors = useColors
        self.allowShutdown = allowShutdown

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
                          self.channels, self.pm_to_nicks, self.status,
                          self.tags, self.notify_events,
                          noticeOnChannel=self.noticeOnChannel,
                          useColors=self.useColors,
                          useRevisions=self.useRevisions,
                          showBlameList=self.showBlameList)
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
    implements(IStatusReceiver)

    in_test_harness = False

    compare_attrs = ["host", "port", "nick", "password",
                     "channels", "pm_to_nicks", "allowForce", "useSSL",
                     "useRevisions", "tags", "useColors",
                     "lostDelay", "failedDelay", "allowShutdown"]

    def __init__(self, host, nick, channels, pm_to_nicks=[], port=6667,
                 allowForce=False, tags=None, password=None, notify_events={},
                 noticeOnChannel=False, showBlameList=True, useRevisions=False,
                 useSSL=False, lostDelay=None, failedDelay=None, useColors=True,
                 allowShutdown=False,
                 categories=None  # deprecated
                 ):
        base.StatusReceiverMultiService.__init__(self)

        if allowForce not in (True, False):
            config.error("allowForce must be boolean, not %r" % (allowForce,))
        if allowShutdown not in (True, False):
            config.error("allowShutdown must be boolean, not %r" % (allowShutdown,))

        # need to stash these so we can detect changes later
        self.host = host
        self.port = port
        self.nick = nick
        self.channels = channels
        self.pm_to_nicks = pm_to_nicks
        self.password = password
        self.allowForce = allowForce
        self.useRevisions = useRevisions
        self.tags = tags or categories
        self.notify_events = notify_events
        self.allowShutdown = allowShutdown

        self.f = IrcStatusFactory(self.nick, self.password,
                                  self.channels, self.pm_to_nicks,
                                  self.tags, self.notify_events,
                                  noticeOnChannel=noticeOnChannel,
                                  useRevisions=useRevisions,
                                  showBlameList=showBlameList,
                                  lostDelay=lostDelay,
                                  failedDelay=failedDelay,
                                  useColors=useColors,
                                  allowShutdown=allowShutdown)

        if useSSL:
            # SSL client needs a ClientContextFactory for some SSL mumbo-jumbo
            if not have_ssl:
                raise RuntimeError("useSSL requires PyOpenSSL")
            cf = ssl.ClientContextFactory()
            c = internet.SSLClient(self.host, self.port, self.f, cf)
        else:
            c = internet.TCPClient(self.host, self.port, self.f)

        c.setServiceParent(self)

    def setServiceParent(self, parent):
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.f.status = parent
        if self.allowForce:
            self.f.control = interfaces.IControl(self.master)

    def stopService(self):
        # make sure the factory will stop reconnecting
        self.f.shutdown()
        return base.StatusReceiverMultiService.stopService(self)
