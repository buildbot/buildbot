# coding: utf-8
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.builtins import range
from future.utils import PY3
from future.utils import text_type

import random
import re
import shlex

from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.python import log
from twisted.python import usage

from buildbot import util
from buildbot import version
from buildbot.data import resultspec
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import utils
from buildbot.util import service

# Used in command_HELLO and it's test. 'Hi' in 100 languages.

GREETINGS = [
    "ږغ كول ، هركلى كول ږغ، هركلى", "Goeie dag", "Tungjatjeta",
    "Yatasay", "Ahlan bik", "Voghdzuyin", "hola", "kaixo", "Horas",
    "Pryvitańnie", "Nomoskar", "Oki", "Selam", "Dez-mat", "Zdrávejte",
    "Mingala ba", "Hola", "Hafa dai", "Oh-see-YOH", "Nín hao", "Bonjou",
    "Zdravo", "Nazdar", "Hallo", "Hallo", "Iiti", "Kotáka", "Saluton", "Tere",
    "Hallo", "Hallo", "Bula", "Helo", "Hei", "Goede morgen", "Bonjour", "Hoi",
    "Ola", "Gamardžoba", "Guten Tag", "Mauri", "Geia!", "Inuugujoq", "Kem cho",
    "Sannu", "Aloha", "Shalóm", "Namasté", "Szia", "Halló", "Hai", "Kiana",
    "Dia is muire dhuit", "Buongiorno", "Kónnichi wa", "Salam",
    "Annyeonghaseyo", "Na", "Sabai dii", "Ave", "Es mīlu tevi", "Labas.",
    "Selamat petang", "Ni hao", "Kia ora", "Yokwe", "Kwe", "sain baina uu",
    "niltze", "Yá'át'ééh", "Namaste", "Hallo.", "Salâm", "Witajcie", "Olá",
    "Kâils", "Aroha", "Salut", "Privét", "Talofa", "Namo namah", "ćao",
    "Nazdar", "Zdravo", "Hola", "Jambo", "Hej", "Sälü", "Halo", "Selam",
    "Sàwàtdee kráp", "Dumela", "Merhaba", "Pryvít", "Adaab arz hai", "Chào",
    "Glidis", "Helo", "Sawubona", "Hoi"]


# This should probably move to the irc class.
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
        return "%c%d%s%c" % (3, irc_colors.index(color), text, 15)
    return text


class UsageError(ValueError):

    def __init__(self, string="Invalid usage", *more):
        ValueError.__init__(self, string, *more)


class ForceOptions(usage.Options):
    optParameters = [
        ["builder", None, None, "which Builder to start"],
        ["codebase", None, "default", "which codebase to build"],
        ["branch", None, "master", "which branch to build"],
        ["revision", None, "HEAD", "which revision to build"],
        ["project", None, "default", "which project to build"],
        ["reason", None, None, "the reason for starting the build"],
        ["props", None, None,
         "A set of properties made available in the build environment, "
         "format is --properties=prop1=value1,prop2=value2,.. "
         "option can be specified multiple times."],
    ]

    def parseArgs(self, *args):
        args = list(args)
        if args:
            if self['builder'] is not None:
                raise UsageError("--builder provided in two ways")
            self['builder'] = args.pop(0)
        if args:  # args might be modified above
            if self['reason'] is not None:
                raise UsageError("--reason provided in two ways")
            self['reason'] = " ".join(args)


class BuildRequest:
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
        if self.useRevisions:
            response = "build containing revision(s) [%s] forced" % s.getRevisions(
            )
        else:
            response = "build #%d forced" % s.getNumber()
        self.parent.send(response)
        self.parent.send("I'll give a shout when the build finishes")
        d = s.waitUntilFinished()
        d.addCallback(self.parent.watchedBuildFinished)


class Contact(service.AsyncService):

    """I hold the state for a single user's interaction with the buildbot.

    There will be one instance of me for each user who interacts personally
    with the buildbot. There will be an additional instance for each
    'broadcast contact' (chat rooms, IRC channels as a whole).
    """

    def __init__(self, bot, user=None, channel=None):
        """
        :param StatusBot bot: StatusBot this Contact belongs to
        :param user: User ID representing this contact
        :param channel: Channel this contact is on (None is used for privmsgs)
        """
        assert user or channel, "At least one of user or channel must be set"

        if user and channel:
            self.name = "Contact(channel=%s, name=%s)" % (channel, user)
        elif channel:
            self.name = "Contact(channel=%s)" % (channel,)
        elif user:
            self.name = "Contact(name=%s)" % (user,)
        service.AsyncService.__init__(self)
        self.bot = bot
        self.notify_events = {}
        self.subscribed = []
        self.build_subscriptions = []
        self.muted = False
        self.useRevisions = bot.useRevisions
        self.useColors = bot.useColors
        self.reported_builds = []  # tuples (when, buildername, buildnum)

        self.user = user
        self.channel = channel
        self._next_HELLO = 'yes?'

    # silliness

    silly = {
        "What happen ?": ["Somebody set up us the bomb."],
        "It's You !!": ["How are you gentlemen !!",
                        "All your base are belong to us.",
                        "You are on the way to destruction."],
        "What you say !!": ["You have no chance to survive make your time.",
                            "HA HA HA HA ...."],
    }

    def startService(self):
        if self.channel and not self.user:
            self.add_notification_events(self.bot.notify_events)
        return service.AsyncService.startService(self)

    def stopService(self):
        self.remove_all_notification_events()

    def doSilly(self, message):
        response = self.silly[message]
        when = 0.5
        for r in response:
            reactor.callLater(when, self.send, r)
            when += 2.5

    def builderMatchesAnyTag(self, builder_tags):
        return any(tag for tag in builder_tags if tag in self.bot.tags)

    @defer.inlineCallbacks
    def getBuilder(self, buildername=None, builderid=None):
        if buildername:
            bdicts = yield self.master.data.get(('builders',),
                                                filters=[resultspec.Filter('name', 'eq', [buildername])])
            if bdicts:
                # Could there be more than one? One is enough.
                bdict = bdicts[0]
            else:
                bdict = None
        elif builderid:
            bdict = yield self.master.data.get(('builders', builderid))
        else:
            raise UsageError("no builder specified")

        if bdict is None:
            if buildername:
                which = '%s' % buildername
            else:
                which = 'number %s' % builderid
            raise UsageError("no such builder '%s'" % which)
        defer.returnValue(bdict)

    def getAllBuilders(self):
        d = self.master.data.get(('builders',))
        return d

    @defer.inlineCallbacks
    def getOnlineBuilders(self):
        all_workers = yield self.master.data.get(('workers',))
        online_builderids = set()
        for worker in all_workers:
            connected = worker['connected_to']
            if not connected:
                continue
            builders = worker['configured_on']
            builderids = [builder['builderid'] for builder in builders]
            online_builderids.update(builderids)
        defer.returnValue(list(online_builderids))

    @defer.inlineCallbacks
    def getRevisionsForBuild(self, bdict):
        # FIXME: Need to get revision info! (build -> buildreq -> buildset ->
        # sourcestamps)
        defer.returnValue(["TODO"])

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

    def shouldReportBuild(self, builder, buildnum):
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
        if not PY3 and isinstance(args, text_type):
            # shlex does not handle unicode.  See
            # http://bugs.python.org/issue1170
            args = args.encode('ascii')
        try:
            return shlex.split(args)
        except ValueError as e:
            raise UsageError(e)

    def command_HELLO(self, args):
        self.send(self._next_HELLO)
        self._next_HELLO = random.choice(GREETINGS)

    def command_VERSION(self, args):
        self.send("buildbot-%s at your service" % version)

    @defer.inlineCallbacks
    def command_LIST(self, args):
        args = self.splitArgs(args)
        if not args:
            raise UsageError("try 'list builders'")

        if args[0] == 'builders':
            bdicts = yield self.getAllBuilders()
            online_builderids = yield self.getOnlineBuilders()

            response = ["Configured builders:"]
            for bdict in bdicts:
                response.append(bdict['name'])
                if bdict['builderid'] not in online_builderids:
                    response.append("[offline]")
            self.send(' '.join(response))
            return
    command_LIST.usage = "list builders - List configured builders"

    @defer.inlineCallbacks
    def command_STATUS(self, args):
        args = self.splitArgs(args)
        if not args:
            which = "all"
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError("try 'status <builder>'")
        if which == "all":
            bdicts = yield self.getAllBuilders()
            for bdict in bdicts:
                yield self.emit_status(bdict['name'])
            return
        yield self.emit_status(which)
    command_STATUS.usage = "status [<which>] - List status of a builder (or all builders)"

    def validate_notification_event(self, event):
        if not re.compile("^(started|finished|success|failure|exception|warnings|"
                          "(success|warnings|exception|failure)To"
                          "(Failure|Success|Warnings|Exception))$").match(event):
            raise UsageError("try 'notify on|off <EVENT>'")

    def list_notified_events(self):
        self.send("The following events are being notified: %r" %
                  sorted(self.notify_events))

    def notify_for(self, *events):
        for event in events:
            if event in self.notify_events:
                return True
        return False

    @defer.inlineCallbacks
    def subscribe_to_build_events(self):
        startConsuming = self.master.mq.startConsuming

        def buildStarted(key, msg):
            return self.buildStarted(msg)

        def buildFinished(key, msg):
            return self.buildFinished(msg)

        for e, f in (("new", buildStarted),             # BuilderStarted
                     ("finished", buildFinished)):      # BuilderFinished
            handle = yield startConsuming(f, ('builders', None, 'builds', None, e))
            self.subscribed.append(handle)

    def unsubscribe_from_build_events(self):
        # Cancel all the subscriptions we have
        old_list, self.subscribed = self.subscribed, []
        for handle in old_list:
            handle.stopConsuming()

    def add_notification_events(self, events):
        for event in events:
            self.validate_notification_event(event)
            self.notify_events[event] = True

            if not self.subscribed:
                self.subscribe_to_build_events()

    def remove_notification_events(self, events):
        for event in events:
            self.validate_notification_event(event)
            del self.notify_events[event]

            if not self.notify_events:
                self.unsubscribe_from_build_events()

    def remove_all_notification_events(self):
        self.notify_events = {}

        if self.subscribed:
            self.unsubscribe_from_build_events()

    def command_NOTIFY(self, args):
        # FIXME: NEED TO THINK ABOUT!
        args = self.splitArgs(args)

        if not args:
            raise UsageError("try 'notify on|off|list [<EVENT>]'")
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

        else:
            raise UsageError("try 'notify on|off|list [<EVENT>]'")

    command_NOTIFY.usage = ("notify on|off|list [<EVENT>] ... - Notify me about build events."
                            "  event should be one or more of: 'started', 'finished', 'failure',"
                            " 'success', 'exception' or 'xToY' (where x and Y are one of success,"
                            " warnings, failure, exception, but Y is capitalized)")

    def getRunningBuilds(self, builderid):
        d = self.master.data.get(('builds',),
                                 filters=[resultspec.Filter('builderid', 'eq', [builderid]),
                                          resultspec.Filter('complete', 'eq', [False])])
        return d

    def getLastCompletedBuild(self, builderid):
        d = self.master.data.get(('builds',),
                                 filters=[resultspec.Filter('builderid', 'eq', [builderid]),
                                          resultspec.Filter('complete', 'eq', [True])],
                                 order=['-number'],
                                 limit=1)

        @d.addCallback
        def listAsOneOrNone(res):
            if res:
                return res[0]
            return None

        return d

    @defer.inlineCallbacks
    def command_WATCH(self, args):
        args = self.splitArgs(args)
        if len(args) != 1:
            raise UsageError("try 'watch <builder>'")

        which = args[0]
        builder = yield self.getBuilder(buildername=which)

        # Get current builds on this builder.
        builds = yield self.getRunningBuilds(builder['builderid'])
        if not builds:
            self.send("there are no builds currently running")
            return

        def watchForCompleteEvent(key, msg):
            if key[-1] == 'complete':
                return self.watchedBuildFinished(msg)

        for build in builds:
            startConsuming = self.master.mq.startConsuming
            handle = yield startConsuming(
                watchForCompleteEvent,
                ('builds', str(build['buildid']), None))
            self.build_subscriptions.append((build['buildid'], handle))

            if self.useRevisions:
                revisions = yield self.getRevisionsForBuild(build)
                r = "watching build %s containing revision(s) [%s] until it finishes" \
                    % (which, ','.join(revisions))
            else:
                r = "watching build %s #%d until it finishes" \
                    % (which, build['number'])

            r += ".."
            self.send(r)
    command_WATCH.usage = "watch <which> - announce the completion of an active build"

    @defer.inlineCallbacks
    def buildStarted(self, build):
        builder = yield self.getBuilder(builderid=build['builderid'])
        builderName = builder['name']
        buildNumber = build['number']
        log.msg('[Contact] Builder %s started' % (builder['name'],))

        # only notify about builders we are interested in
        if (self.bot.tags is not None and
                not self.builderMatchesAnyTag(builder.get('tags', []))):
            log.msg('Not notifying for a build that does not match any tags')
            return

        if not self.notify_for('started'):
            return

        if self.useRevisions:
            revisions = yield self.getRevisionsForBuild(build)
            r = "build containing revision(s) [%s] on %s started" % \
                (','.join(revisions), builderName)
        else:
            # Abbreviate long lists of changes to simply two
            # revisions, and the number of additional changes.
            # TODO: We can't get the list of the changes related to a build in
            # nine
            changes_str = ""

            r = "build #%d of %s started" % (buildNumber, builderName)
            if changes_str:
                r += " (%s)" % changes_str

        self.send(r)

    @defer.inlineCallbacks
    def buildFinished(self, build):
        builder = yield self.getBuilder(builderid=build['builderid'])
        builderName = builder['name']
        buildNumber = build['number']
        buildResult = build['results']

        # only notify about builders we are interested in
        if (self.bot.tags is not None and
                not self.builderMatchesAnyTag(builder.get('tags', []))):
            log.msg('Not notifying for a build that does not match any tags')
            return

        if not (yield self.notify_for_finished(build)):
            return

        if not self.shouldReportBuild(builderName, buildNumber):
            return

        results = self.getResultsDescriptionAndColor(buildResult)

        if self.useRevisions:
            revisions = yield self.getRevisionsForBuild(build)
            r = "Build %s containing revision(s) [%s] is complete: %s" % \
                (builderName, ','.join(revisions), results[0])
        else:
            r = "Build %s #%d is complete: %s" % \
                (builderName, buildNumber, results[0])

        r += ' [%s]' % maybeColorize(build['state_string'],
                                     results[1], self.useColors)

        # FIXME: where do we get the list of changes for a build ?
        # if self.bot.showBlameList and buildResult != SUCCESS and len(build.changes) != 0:
        #    r += '  blamelist: ' + ', '.join(list(set([c.who for c in build.changes])))
        r += " - %s" % utils.getURLForBuild(
            self.master, builder['builderid'], buildNumber)
        self.send(r)

    results_descriptions = {
        SUCCESS: ("Success", 'GREEN'),
        WARNINGS: ("Warnings", 'YELLOW'),
        FAILURE: ("Failure", 'RED'),
        EXCEPTION: ("Exception", 'PURPLE'),
        RETRY: ("Retry", 'AQUA_LIGHT'),
        CANCELLED: ("Cancelled", 'PINK'),
    }

    def getResultsDescriptionAndColor(self, results):
        return self.results_descriptions.get(results, ("??", 'RED'))

    @defer.inlineCallbacks
    def notify_for_finished(self, build):
        if self.notify_for('finished'):
            defer.returnValue(True)

        if self.notify_for(self.results_descriptions.get(build['results'])[0].lower()):
            defer.returnValue(True)

        prevBuild = yield self.master.data.get(
            ('builders', build['builderid'], 'builds', build['number'] - 1))
        if prevBuild:
            prevResult = prevBuild['results']

            required_notification_control_string = ''.join(
                (self.results_descriptions.get(prevResult)[0].lower(),
                 'To',
                 self.results_descriptions.get(build['results'])[0].capitalize()))

            if (self.notify_for(required_notification_control_string)):
                defer.returnValue(True)

        defer.returnValue(False)

    @defer.inlineCallbacks
    def watchedBuildFinished(self, build):
        builder = yield self.getBuilder(builderid=build['builderid'])

        # only notify about builders we are interested in
        if (self.bot.tags is not None and
                not self.builderMatchesAnyTag(builder.get('tags', []))):
            log.msg('Not notifying for a build that does not match any tags')
            return

        builder_name = builder['name']
        buildnum = build['number']

        if not self.shouldReportBuild(builder_name, buildnum):
            return

        results = self.getResultsDescriptionAndColor(build['results'])
        if self.useRevisions:
            revisions = yield self.getRevisionsForBuild(build)
            r = "Build %s containing revision(s) [%s] is complete: %s" % \
                (builder_name, ','.join(revisions), results[0])
        else:
            r = "Build %s #%d is complete: %s" % \
                (builder_name, buildnum, results[0])

        r += ' [%s]' % maybeColorize(build['state_string'],
                                     results[1], self.useColors)

        r += " - %s" % utils.getURLForBuild(
            self.master, builder['builderid'], buildnum)

        self.send(r)

    @defer.inlineCallbacks
    def command_FORCE(self, args):
        # FIXME: NEED TO THINK ABOUT!
        errReply = "try '%s'" % (self.command_FORCE.usage)
        args = self.splitArgs(args)
        if not args:
            raise UsageError(errReply)
        what = args.pop(0)
        if what != "build":
            raise UsageError(errReply)
        opts = ForceOptions()
        opts.parseOptions(args)

        builderName = opts['builder']
        builder = yield self.getBuilder(buildername=builderName)
        branch = opts['branch']
        revision = opts['revision']
        codebase = opts['codebase']
        project = opts['project']
        reason = opts['reason']
        props = opts['props']

        if builderName is None:
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
                    log.msg("bad property name='%s', value='%s'" %
                            (pname, pvalue))
                    self.send("sorry, bad property name='%s', value='%s'" %
                              (pname, pvalue))
                    return
                properties.setProperty(pname, pvalue, "Force Build chat")

        reason = u"forced: by %s: %s" % (self.describeUser(), reason)
        try:
            yield self.master.data.updates.addBuildset(builderids=[builder['builderid']],
                                                       # For now, we just use
                                                       # this as the id.
                                                       scheduler=u"status.words",
                                                       sourcestamps=[{
                                                           'codebase': codebase, 'branch': branch,
                                                           'revision': revision, 'project': project,
                                                           'repository': "null"}],
                                                       reason=reason,
                                                       properties=properties.asDict(),
                                                       waited_for=False)
        except AssertionError as e:
            self.send("I can't: " + str(e))

    command_FORCE.usage = ("force build [--codebase=CODEBASE] [--branch=branch] [--revision=revision]"
                           " [--props=prop1=val1,prop2=val2...] <which> <reason> - Force a build")

    @defer.inlineCallbacks
    def command_STOP(self, args):
        args = self.splitArgs(args)
        if len(args) < 3 or args[0] != 'build':
            raise UsageError("try 'stop build WHICH <REASON>'")
        which = args[1]
        reason = args[2]

        r = "stopped: by %s: %s" % (self.describeUser(), reason)

        # find an in-progress build
        builder = yield self.getBuilder(buildername=which)
        builds = yield self.getRunningBuilds(builder['builderid'])

        if not builds:
            self.send("sorry, no build is currently running")
            return

        for bdict in builds:
            num = bdict['number']

            yield self.master.data.control('stop', {'reason': r},
                                           ('builders', builder['builderid'], 'builds', num))

            if self.useRevisions:
                revisions = yield self.getRevisionsForBuild(bdict)
                response = "build containing revision(s) [%s] interrupted" % ','.join(
                    revisions)
            else:
                response = "build %d interrupted" % num
            self.send(response)

    command_STOP.usage = "stop build <which> <reason> - Stop a running build"

    def getCurrentBuildstep(self, build):
        d = self.master.data.get(('builds', build['buildid'], 'steps'),
                                 filters=[
                                     resultspec.Filter('complete', 'eq', [False])],
                                 order=['number'],
                                 limit=1)
        return d

    @defer.inlineCallbacks
    def emit_status(self, which):
        response = '%s: ' % which

        builder = yield self.getBuilder(buildername=which)
        runningBuilds = yield self.getRunningBuilds(builder['builderid'])

        if not runningBuilds:
            onlineBuilders = yield self.getOnlineBuilders()
            if builder['builderid'] in onlineBuilders:
                response += "idle"
                lastBuild = yield self.getLastCompletedBuild(builder['builderid'])
                if lastBuild:
                    complete_at = lastBuild['complete_at']
                    if complete_at:
                        complete_at = util.datetime2epoch(complete_at)
                        ago = self.convertTime(int(util.now() - complete_at))
                    else:
                        ago = "??"
                    status = lastBuild['state_string']
                    response += ' last build %s ago: %s' % (ago, status)
            else:
                response += "offline"
        else:
            response += "running:"
            buildInfo = []
            for build in runningBuilds:
                step = yield self.getCurrentBuildstep(build)
                if step:
                    s = "(%s)" % step['state_string']
                else:
                    s = "(no current step)"
                buildInfo.append("%d %s" % (build['number'], s))

            response += ' ' + ', '.join(buildInfo)

        self.send(response)

    @defer.inlineCallbacks
    def command_LAST(self, args):
        # FIXME: NEED TO THINK ABOUT!
        args = self.splitArgs(args)

        if not args:
            builders = yield self.getAllBuilders()
        elif len(args) == 1:
            builder = yield self.getBuilder(buildername=args[0])
            if not builder:
                raise UsageError("no such builder")
            builders = [builder]
        else:
            raise UsageError("try 'last <builder>'")

        for builder in builders:
            lastBuild = yield self.getLastCompletedBuild(builder['builderid'])
            if not lastBuild:
                status = "(no builds run since last restart)"
            else:
                complete_at = lastBuild['complete_at']
                if complete_at:
                    complete_at = util.datetime2epoch(complete_at)
                    ago = self.convertTime(int(util.now() - complete_at))
                else:
                    ago = "??"
                status = lastBuild['state_string']
                status = 'last build %s ago: %s' % (ago, status)
            self.send("last build [%s]: %s" % (builder['name'], status))

    command_LAST.usage = "last <which> - list last build status for builder <which>"

    def build_commands(self):
        commands = []
        for k in dir(self):
            if k.startswith('command_'):
                commands.append(k[8:].lower())
        commands.sort()
        return commands

    def describeUser(self):
        if self.channel:
            return "User <%s> on channel %s" % (self.user, self.channel)
        return "User <%s> (privmsg)" % self.user

    # commands

    def command_MUTE(self, args):
        # The order of these is important! ;)
        self.send("Shutting up for now.")
        self.muted = True
    command_MUTE.usage = "mute - suppress all messages until a corresponding 'unmute' is issued"

    def command_UNMUTE(self, args):
        if self.muted:
            # The order of these is important! ;)
            self.muted = False
            self.send("I'm baaaaaaaaaaack!")
        else:
            self.send(
                "You hadn't told me to be quiet, but it's the thought that counts, right?")
    command_UNMUTE.usage = "unmute - disable a previous 'mute'"

    def command_HELP(self, args):
        # FIXME: NEED TO THINK ABOUT!
        args = self.splitArgs(args)
        if not args:
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
            self.send(
                "No usage info for " + ' '.join(["'%s'" % arg for arg in args]))
    command_HELP.usage = ("help <command> [<arg> [<subarg> ...]] - "
                          "Give help for <command> or one of it's arguments")

    def command_SOURCE(self, args):
        self.send("My source can be found at "
                  "https://github.com/buildbot/buildbot")
    command_SOURCE.usage = "source - the source code for Buildbot"

    def command_COMMANDS(self, args):
        commands = self.build_commands()
        str = "buildbot commands: " + ", ".join(commands)
        self.send(str)
    command_COMMANDS.usage = "commands - List available commands"

    def command_DESTROY(self, args):
        if self.bot.nickname not in args:
            self.act("readies phasers")

    def command_DANCE(self, args):
        reactor.callLater(1.0, self.send, "<(^.^<)")
        reactor.callLater(2.0, self.send, "<(^.^)>")
        reactor.callLater(3.0, self.send, "(>^.^)>")
        reactor.callLater(3.5, self.send, "(7^.^)7")
        reactor.callLater(5.0, self.send, "(>^.^<)")

    def command_HUSTLE(self, args):
        self.act("does the hustle")
    command_HUSTLE.usage = "dondon on #qutebrowser: qutebrowser-bb needs to learn to do the hustle"

    def command_SHUTDOWN(self, args):
        # FIXME: NEED TO THINK ABOUT!
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
        if self.muted:
            return

        if self.channel:
            self.bot.groupChat(self.channel, message)
        else:
            self.bot.chat(self.user, message)

    def act(self, action):
        if self.muted:
            return

        self.bot.groupDescribe(self.channel, action)

    # main dispatchers for incoming messages

    def getCommandMethod(self, command):
        return getattr(self, 'command_' + command.upper(), None)

    # FIXME: this returns a deferred, but nothing uses it!
    def handleMessage(self, message):
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
            d = defer.maybeDeferred(meth, args.strip())

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

    def handleAction(self, action):
        # this is sent when somebody performs an action that mentions the
        # buildbot (like '/me kicks buildbot'). 'self.user' is the name/nick/id of
        # the person who performed the action, so if their action provokes a
        # response, they can be named.  This is 100% silly.
        if not action.endswith("s " + self.bot.nickname):
            return
        words = action.split()
        verb = words[-2]
        if verb == "kicks":
            response = "%s back" % verb
        elif verb == "threatens":
            response = "hosts a red wedding for %s" % self.user
        else:
            response = "%s %s too" % (verb, self.user)
        self.act(response)


class StatusBot(service.AsyncMultiService):

    """ Abstract status bot """

    contactClass = Contact

    def __init__(self, tags, notify_events,
                 useRevisions=False, showBlameList=False, useColors=True,
                 categories=None  # deprecated
                 ):
        service.AsyncMultiService.__init__(self)
        self.tags = tags or categories
        self.notify_events = notify_events
        self.useColors = useColors
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self.contacts = {}

    def groupChat(self, channel, message):
        """ Write a message on a channel """
        raise NotImplementedError

    def chat(self, user, message):
        """ Write a message to a user """
        raise NotImplementedError

    def groupDescribe(self, channel, message):
        """ Describe what we are doing on a channel """
        raise NotImplementedError

    def getContact(self, user=None, channel=None):
        """ get a Contact instance for ``user`` on ``channel`` """
        try:
            return self.contacts[(channel, user)]
        except KeyError:
            new_contact = self.contactClass(self, user=user, channel=channel)
            self.contacts[(channel, user)] = new_contact
            new_contact.setServiceParent(self)
            return new_contact

    def log(self, msg):
        log.msg("%s: %s" % (self, msg))


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
