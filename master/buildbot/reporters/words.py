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

import random
import re
import shlex
import types

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
from buildbot.process.results import statusToString
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


class UsageError(ValueError):

    # pylint: disable=useless-super-delegation
    def __init__(self, string="Invalid usage", *more):
        # This is not useless as we change the default value of an argument.
        # This bug is reported as "fixed" but apparently, it is not.
        # https://github.com/PyCQA/pylint/issues/1085
        # (Maybe there is a problem with builtin exceptions).
        super().__init__(string, *more)


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


dangerous_commands = []

def dangerousCommand(method):
    command = method.__name__
    if not command.startswith('command_'):
        raise ValueError('@dangerous can be used only for commands')
    dangerous_commands.append(command[8:])
    return method


class Contact(service.AsyncService):

    """I hold the state for a single user's interaction with the buildbot.

    There will be one instance of me for each user who interacts personally
    with the buildbot. There will be an additional instance for each
    'broadcast contact' (chat rooms, IRC channels as a whole).
    """

    def __init__(self, bot, user=None, channel=None, _reactor=reactor):
        """
        :param StatusBot bot: StatusBot this Contact belongs to
        :param user: User ID representing this contact
        :param channel: Channel this contact is on (None is used for privmsgs)
        """
        assert user or channel, "At least one of user or channel must be set"

        if user and channel:
            self.name = "Contact(channel={}, name={})".format(channel, user)
        elif channel:
            self.name = "Contact(channel={})".format(channel, )
        elif user:
            self.name = "Contact(name={})".format(user, )
        super().__init__()
        self.bot = bot
        self.notify_events = set()
        self.subscribed = []
        self.build_subscriptions = []
        self.useRevisions = bot.useRevisions

        self.user = user
        self.channel = channel
        self._next_HELLO = 'yes?'

        self.reactor = _reactor

    @staticmethod
    def overrideCommand(meth):
        try:
            base_meth = getattr(Contact, meth.__name__)
        except AttributeError:
            pass
        else:
            try: meth.__doc__ = base_meth.__doc__
            except AttributeError: pass
            try: meth.usage = base_meth.usage
            except AttributeError: pass
        return meth

    results_descriptions = {
        SUCCESS: "completed successfully",
        WARNINGS: "completed with warnings",
        FAILURE: "failed",
        EXCEPTION: "stopped with exception",
        RETRY: "has been retried",
        CANCELLED: "was cancelled",
    }

    def format_build_status(self, build, short=False):
        """ Optionally add color to the message """
        return self.results_descriptions[build['results']]

    @property
    def userid(self):
        return self.user

    @property
    def channelid(self):
        return self.channel if self.channel is not None else self.user

    # Silliness

    silly = {
        "What happen ?": ["Somebody set up us the bomb."],
        "It's You !!": ["How are you gentlemen !!",
                        "All your base are belong to us.",
                        "You are on the way to destruction."],
        "What you say !!": ["You have no chance to survive make your time.",
                            "HA HA HA HA ...."],
    }

    # Communication with the user

    def send(self, message):
        if isinstance(message, (list, tuple, types.GeneratorType)):
            message = "\n".join(message)
        return self.bot.send_message(self.channel, message)

    def access_denied(self, *args):
        self.send("Thou shall not pass, {}!!!".format(self.user))

    # Main dispatchers for incoming messages

    def getCommandMethod(self, command, ignore_authz=False):
        command = command.upper()
        try:
            method = getattr(self, 'command_' + command)
        except AttributeError:
            return
        if not ignore_authz:
            get_authz = self.bot.authz.get
            acl = get_authz(command)
            if acl is None:
                if command in dangerous_commands:
                    acl = False
                else:
                    acl = get_authz('', True)
                acl = get_authz('!', acl)
            if isinstance(acl, (list, tuple)):
                acl = self.userid in acl
            if not acl:
                return self.access_denied
        return method

    def handleMessage(self, message, **kwargs):
        message = message.lstrip()
        if message in self.silly:
            self.doSilly(message)
            return defer.succeed(None)

        parts = message.split(' ', 1)
        if len(parts) == 1:
            parts = parts + ['']
        cmd, args = parts

        cmd_suffix = self.bot.commandSuffix
        if cmd_suffix and cmd.endswith(cmd_suffix):
            cmd = cmd[:-len(cmd_suffix)]

        log.msg("chat bot command", cmd)

        if cmd.startswith(self.bot.commandPrefix):
            meth = self.getCommandMethod(cmd[len(self.bot.commandPrefix):])
        else:
            meth = None

        if not meth and message[-1] == '!':
            self.send("What you say!")
            return defer.succeed(None)

        if meth:
            d = defer.maybeDeferred(meth, args.strip(), **kwargs)

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

    def startService(self):
        if self.channel and self.user is None:
            self.add_notification_events(self.bot.notify_events)
        return super().startService()

    def stopService(self):
        self.remove_all_notification_events()

    def doSilly(self, message):
        response = self.silly[message]
        when = 0.5
        for r in response:
            self.reactor.callLater(when, self.send, r)
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
                which = buildername
            else:
                which = 'number {}'.format(builderid)
            raise UsageError("no such builder '{}'".format(which))
        return bdict

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
        return list(online_builderids)

    @defer.inlineCallbacks
    def getRevisionsForBuild(self, bdict):
        # FIXME: Need to get revision info! (build -> buildreq -> buildset ->
        # sourcestamps)
        return ["TODO"]

    def convertTime(self, seconds):
        if seconds <= 1:
            return "a moment"
        if seconds < 20:
            return "{:d} seconds".format(seconds)
        if seconds < 55:
            return "{:d} seconds".format(round(seconds / 10) * 10)
        minutes = round(seconds / 60)
        if minutes == 1:
            return "a minute"
        if minutes < 20:
            return "{:d} minutes".format(minutes)
        if minutes < 55:
            return "{:d} minutes".format(round(minutes / 10) * 10)
        hours = round(minutes / 60)
        if hours == 1:
            return "an hour"
        if hours < 24:
            return "{:d} hours".format(hours)
        days = (hours+6) // 24
        if days == 1:
            return "a day"
        if days < 30:
            return "{:d} days".format(days)
        months = int((days+10) / 30.5)
        if months == 1:
            return "a month"
        if months < 12:
            return "{} months".format(months)
        years = round(days / 365.25)
        if years == 1:
            return "a year"
        return "{} years".format(years)

    def shouldReportBuild(self, builder, buildnum):
        """Returns True if this build should be reported for this contact
        (eliminating duplicates), and also records the report for later"""
        reported_builds = self.bot.reported_builds.setdefault(self.channelid, [])

        for w, b, n in reported_builds:
            if b == builder and n == buildnum:
                return False
        reported_builds.append([util.now(), builder, buildnum])

        # clean the reported builds
        horizon = util.now() - 60
        while reported_builds and reported_builds[0][0] < horizon:
            reported_builds.pop(0)

        # and return True, since this is a new one
        return True

    def splitArgs(self, args):
        """Returns list of arguments parsed by shlex.split() or
        raise UsageError if failed"""
        try:
            return shlex.split(args)
        except ValueError as e:
            raise UsageError(e)

    def command_HELLO(self, args, **kwargs):
        """say hello"""
        self.send(self._next_HELLO)
        self._next_HELLO = random.choice(GREETINGS)

    def command_VERSION(self, args, **kwargs):
        """show buildbot version"""
        self.send("This is buildbot-{} at your service".format(version))

    @defer.inlineCallbacks
    def command_LIST(self, args, **kwargs):
        """list configured builders"""
        args = self.splitArgs(args)
        if not args:
            raise UsageError("Try '"+self.bot.commandPrefix+"list builders'.")

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
    def command_STATUS(self, args, **kwargs):
        """list status of a builder (or all builders)"""
        args = self.splitArgs(args)
        if not args:
            which = "all"
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError("Try '"+self.bot.commandPrefix+"status _builder_'.")
        results = []
        if which == "all":
            bdicts = yield self.getAllBuilders()
            for bdict in bdicts:
                status = yield self.get_status(bdict['name'], short=True)
                results.append(status)
        else:
            status = yield self.get_status(which)
            results.append(status)
        if results:
            self.send(results)
    command_STATUS.usage = "status [_which_] - List status of a builder (or all builders)"

    def validate_notification_event(self, event):
        if not re.compile("^(started|finished|success|warnings|failure|exception|"
                          "problem|recovery|worse|better|"
                          # this is deprecated list 
                          "(success|warnings|failure|exception)To"
                          "(Success|Warnings|Failure|Exception))$").match(event):
            raise UsageError("Try '"+self.bot.commandPrefix+"notify on|off _EVENT_'.")

    def list_notified_events(self):
        self.send("The following events are being notified: {}"
                  .format(", ".join(sorted(self.notify_events))))

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
            self.notify_events.add(event)

        if not self.subscribed:
            self.subscribe_to_build_events()

    def remove_notification_events(self, events):
        for event in events:
            self.validate_notification_event(event)
            self.notify_events.remove(event)

            if not self.notify_events:
                self.unsubscribe_from_build_events()

    def remove_all_notification_events(self):
        self.notify_events = set()

        if self.subscribed:
            self.unsubscribe_from_build_events()

    def command_NOTIFY(self, args, **kwargs):
        """notify me about build events"""
        args = self.splitArgs(args)

        if not args:
            raise UsageError("Try '"+self.bot.commandPrefix+"notify on|off|list [_EVENT_]'.")
        action = args.pop(0)
        events = args

        if action in ("on", "on-quiet"):
            if not events:
                events = ('started', 'finished')
            self.add_notification_events(events)

            if action == "on":
                self.list_notified_events()
            self.bot.saveNotifyContacts()

        elif action in ("off", "off-quiet"):
            if events:
                self.remove_notification_events(events)
            else:
                self.remove_all_notification_events()

            if action == "off":
                self.list_notified_events()
            self.bot.saveNotifyContacts()

        elif action == "list":
            self.list_notified_events()

        else:
            raise UsageError("Try '"+self.bot.commandPrefix+"notify on|off|list [_EVENT_]'.")

    command_NOTIFY.usage = ("notify on|off|list [_EVENT_] ... - notify me about build events;"
                            "  event should be one or more of: 'started', 'finished', 'failure',"
                            " 'success', 'exception', 'problem', 'recovery', 'better', or 'worse'")

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
    def command_WATCH(self, args, **kwargs):
        """announce the completion of an active build"""
        args = self.splitArgs(args)
        if len(args) != 1:
            raise UsageError("Try '"+self.bot.commandPrefix+"watch _builder_'.")

        which = args[0]
        builder = yield self.getBuilder(buildername=which)

        # Get current builds on this builder.
        builds = yield self.getRunningBuilds(builder['builderid'])
        if not builds:
            self.send("There are no currently running builds.")
            return

        def watchForCompleteEvent(key, msg):
            if key[-1] in ('finished', 'complete'):
                return self.buildFinished(msg, watched=True)

        for build in builds:
            startConsuming = self.master.mq.startConsuming
            handle = yield startConsuming(
                watchForCompleteEvent,
                ('builds', str(build['buildid']), None))
            self.build_subscriptions.append((build['buildid'], handle))

            url = utils.getURLForBuild(self.master, builder['builderid'], build['number'])

            if self.useRevisions:
                revisions = yield self.getRevisionsForBuild(build)
                r = "Watching build on `{}` containing revision(s) {} until it finishes..." \
                    .format(which, ','.join(revisions))
            else:
                r = "Watching build [#{:d}]({}) of `{}` until it finishes..." \
                    .format(build['number'], url, which)

            self.send(r)
    command_WATCH.usage = "watch _which_ - announce the completion of an active build"

    @defer.inlineCallbacks
    def buildStarted(self, build):
        builder = yield self.getBuilder(builderid=build['builderid'])
        builderName = builder['name']
        buildNumber = build['number']
        log.msg('[Contact] Builder {} started'.format(builder['name'], ))

        # only notify about builders we are interested in
        if (self.bot.tags is not None and
                not self.builderMatchesAnyTag(builder.get('tags', []))):
            log.msg('Not notifying for a build that does not match any tags')
            return

        if not self.notify_for('started'):
            return

        if self.useRevisions:
            revisions = yield self.getRevisionsForBuild(build)
            r = "Build containing revision(s) {} on {} started" \
                .format(','.join(revisions), builderName)
        else:
            # Abbreviate long lists of changes to simply two
            # revisions, and the number of additional changes.
            # TODO: We can't get the list of the changes related to a build in
            # nine
            changes_str = ""

            url = utils.getURLForBuild(self.master, builder['builderid'], build['number'])
            r = "Build [#{:d}]({}) of `{}` started".format(buildNumber, url, builderName)
            if changes_str:
                r += " ({})".format(changes_str)

        self.send(r+'.')

    @defer.inlineCallbacks
    def buildFinished(self, build, watched=False):
        builder = yield self.getBuilder(builderid=build['builderid'])
        builderName = builder['name']
        buildNumber = build['number']

        # only notify about builders we are interested in
        if (self.bot.tags is not None and
                not self.builderMatchesAnyTag(builder.get('tags', []))):
            log.msg('Not notifying for a build that does not match any tags')
            return

        if not (watched or (yield self.notify_for_finished(build))):
            return

        if not self.shouldReportBuild(builderName, buildNumber):
            return

        url = utils.getURLForBuild(self.master, builder['builderid'], buildNumber)

        if self.useRevisions:
            revisions = yield self.getRevisionsForBuild(build)
            r = "Build on `{}` containing revision(s) {} {}" \
                .format(builderName, ','.join(revisions), self.format_build_status(build))
        else:
            r = "Build [#{:d}]({}) of `{}` {}" \
                .format(buildNumber, url, builderName, self.format_build_status(build))

        s = build.get('status_string')
        if build['results'] != SUCCESS and s is not None:
            r += ": " + s
        else:
            r += "."

        # FIXME: where do we get the list of changes for a build ?
        # if self.bot.showBlameList and buildResult != SUCCESS and len(build.changes) != 0:
        #    r += '  blamelist: ' + ', '.join(list(set([c.who for c in build.changes])))
        self.send(r)

    @defer.inlineCallbacks
    def notify_for_finished(self, build):
        if self.notify_for('finished'):
            return True

        result = build['results']
        result_name = statusToString(result)
        if self.notify_for(result_name):
            return True

        if result in (SUCCESS, WARNINGS, FAILURE, EXCEPTION):
            prev_build = yield self.master.data.get(
                ('builders', build['builderid'], 'builds', build['number'] - 1))
            if prev_build:
                prev_result = prev_build['results']

                if prev_result in (SUCCESS, WARNINGS, FAILURE, EXCEPTION):
                    if self.notify_for('better') and result < prev_result:
                        return True
                    if self.notify_for('worse') and result > prev_result:
                        return True

                    if self.notify_for('problem') \
                            and prev_result in (SUCCESS, WARNINGS) \
                            and result in (FAILURE, EXCEPTION):
                        return True

                    if self.notify_for('recovery') \
                            and prev_result in (FAILURE, EXCEPTION) \
                            and result in (SUCCESS, WARNINGS):
                        return True

                    # DEPRECATED
                    required_notification_control_string = ''.join(
                        (statusToString(prev_result).lower(),
                         'To',
                         result_name.capitalize()))
                    if (self.notify_for(required_notification_control_string)):
                        return True

        return False

    @defer.inlineCallbacks
    @dangerousCommand
    def command_FORCE(self, args, **kwargs):
        """force a build"""

        # FIXME: NEED TO THINK ABOUT!
        errReply = "Try '{}{}'".format(self.bot.commandPrefix, self.command_FORCE.usage)
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
            log.msg("bad branch '{}'".format(branch))
            self.send("sorry, bad branch '{}'".format(branch))
            return
        if revision and not revision_validate.match(revision):
            log.msg("bad revision '{}'".format(revision))
            self.send("sorry, bad revision '{}'".format(revision))
            return

        properties = Properties()
        properties.master = self.master

        if props:
            # split props into name:value dict
            pdict = {}
            propertylist = props.split(",")
            for prop in propertylist:
                splitproperty = prop.split("=", 1)
                pdict[splitproperty[0]] = splitproperty[1]

            # set properties
            for prop in pdict:
                pname = prop
                pvalue = pdict[prop]
                if not pname_validate.match(pname) \
                        or not pval_validate.match(pvalue):
                    log.msg("bad property name='{}', value='{}'"
                            .format(pname, pvalue))
                    self.send("sorry, bad property name='{}', value='{}'"
                              .format(pname, pvalue))
                    return
                properties.setProperty(pname, pvalue, "Force Build chat")

        reason = "forced: by {}: {}".format(self.describeUser(), reason)
        try:
            yield self.master.data.updates.addBuildset(builderids=[builder['builderid']],
                                                       # For now, we just use
                                                       # this as the id.
                                                       scheduler="status.words",
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
                           " [--props=prop1=val1,prop2=val2...] _which_ _reason_ - Force a build")

    @defer.inlineCallbacks
    @dangerousCommand
    def command_STOP(self, args, **kwargs):
        """stop a running build"""
        args = self.splitArgs(args)
        if len(args) < 3 or args[0] != 'build':
            raise UsageError("Try '"+self.bot.commandPrefix+"stop build _which_ _reason_'.")
        which = args[1]
        reason = ' '.join(args[2:])

        r = "stopped: by {}: {}".format(self.describeUser(), reason)

        # find an in-progress build
        builder = yield self.getBuilder(buildername=which)
        builderid = builder['builderid']
        builds = yield self.getRunningBuilds(builderid)

        if not builds:
            self.send("Sorry, no build is currently running.")
            return

        for bdict in builds:
            num = bdict['number']

            yield self.master.data.control('stop', {'reason': r},
                                           ('builders', builderid, 'builds', num))
            if self.useRevisions:
                revisions = yield self.getRevisionsForBuild(bdict)
                response = "Build containing revision(s) {} interrupted".format(','.join(
                    revisions))
            else:
                url = utils.getURLForBuild(self.master, builderid, num)
                response = "Build [#{:d}]({}) of `{}` interrupted.".format(num, url, which)
            self.send(response)

    command_STOP.usage = "stop build _which_ _reason_ - Stop a running build"

    def getCurrentBuildstep(self, build):
        d = self.master.data.get(('builds', build['buildid'], 'steps'),
                                 filters=[
                                     resultspec.Filter('complete', 'eq', [False])],
                                 order=['number'],
                                 limit=1)
        return d

    @defer.inlineCallbacks
    def get_status(self, which, short=False):
        response = '`{}`: '.format(which)

        builder = yield self.getBuilder(buildername=which)
        builderid = builder['builderid']
        runningBuilds = yield self.getRunningBuilds(builderid)

        if not runningBuilds:
            onlineBuilders = yield self.getOnlineBuilders()
            if builderid in onlineBuilders:
                response += "idle 😴"
                lastBuild = yield self.getLastCompletedBuild(builderid)
                if lastBuild:
                    complete_at = lastBuild['complete_at']
                    if complete_at:
                        complete_at = util.datetime2epoch(complete_at)
                        ago = self.convertTime(int(self.reactor.seconds() -
                                                   complete_at))
                    else:
                        ago = "??"
                    status = self.format_build_status(lastBuild, short=short)
                    if not short:
                        status = ", " + status
                        if lastBuild['results'] != SUCCESS:
                            status += ": " + lastBuild['status_string']
                    response += ': last build {} ago{}'.format(ago, status)
            else:
                response += "offline 💀"
        else:
            response += "running 🤠:"
            buildInfo = []
            for build in runningBuilds:
                step = yield self.getCurrentBuildstep(build)
                if step:
                    s = "({})".format(step[-1]['state_string'])
                else:
                    s = "(no current step)"
                bnum = build['number']
                url = utils.getURLForBuild(self.master, builderid, bnum)
                buildInfo.append("build [#{:d}]({}) {}".format(bnum, url, s))

            response += ' ' + ', '.join(buildInfo)

        return response

    @defer.inlineCallbacks
    def command_LAST(self, args, **kwargs):
        """list last build status for a builder"""
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
            raise UsageError("Try '"+self.bot.commandPrefix+"last _builder_'.")

        messages = []

        for builder in builders:
            lastBuild = yield self.getLastCompletedBuild(builder['builderid'])
            if not lastBuild:
                status = "no builds run since last restart"
            else:
                complete_at = lastBuild['complete_at']
                if complete_at:
                    complete_at = util.datetime2epoch(complete_at)
                    ago = self.convertTime(int(self.reactor.seconds() -
                                               complete_at))
                else:
                    ago = "??"
                status = self.format_build_status(lastBuild)
                status = 'last build {} ({} ago)'.format(status, ago)
                if lastBuild['results'] != SUCCESS:
                    status += ': {}'.format(lastBuild['state_string'])
            messages.append("`{}`: {}".format(builder['name'], status))
        if messages:
            self.send(messages)

    command_LAST.usage = "last [_which_] - list last build status for builder _which_"

    def build_commands(self):
        commands = []
        for k in dir(self):
            if k.startswith('command_'):
                commands.append(self.bot.commandPrefix + k[8:].lower())
        commands.sort()
        return commands

    def describeUser(self):
        if self.channel:
            return "User <{}> on {}".format(self.user, self.channel)
        return "User <{}>".format(self.user)

    # commands

    def command_HELP(self, args, **kwargs):
        """give help for a command or one of it's arguments"""
        args = self.splitArgs(args)
        lp = len(self.bot.commandPrefix)
        if not args:
            commands = self.build_commands()
            results = []
            for command in commands:
                meth = self.getCommandMethod(command[lp:], True)
                doc = getattr(meth, '__doc__', None)
                if doc:
                    results.append("{} - {}".format(command, doc))
            if results:
                self.send(results)
            return
        command = args[0]
        if command.startswith(self.bot.commandPrefix):
            command = command[lp:]
        meth = self.getCommandMethod(command, True)
        if not meth:
            raise UsageError("There is no such command '{}'.".format(args[0]))
        doc = getattr(meth, 'usage', None)
        if isinstance(doc, dict):
            if len(args) == 1:
                k = None  # command
            elif len(args) == 2:
                k = args[1]  # command arg
            else:
                k = tuple(args[1:])  # command arg subarg ...
            doc = doc.get(k, None)
        if doc:
            self.send("Usage: {}{}".format(self.bot.commandPrefix, doc))
        else:
            self.send(
                "No usage info for " + ' '.join(["'{}'".format(arg) for arg in args]))
    command_HELP.usage = ("help [_command_ _arg_ [_subarg_ ...]] - "
                          "Give help for _command_ or one of it's arguments")

    def command_SOURCE(self, args, **kwargs):
        "the source code for buildbot"
        self.send("My source can be found at "
                  "https://github.com/buildbot/buildbot")
    command_SOURCE.usage = "source - the source code for Buildbot"

    def command_COMMANDS(self, args, **kwargs):
        """list available commands"""
        commands = self.build_commands()
        str = "Buildbot commands: " + ", ".join(commands)
        self.send(str)
    command_COMMANDS.usage = "commands - List available commands"

    def command_DANCE(self, args, **kwargs):
        """dance, dance academy..."""
        self.reactor.callLater(1.0, self.send, "<(^.^<)")
        self.reactor.callLater(2.0, self.send, "<(^.^)>")
        self.reactor.callLater(3.0, self.send, "(>^.^)>")
        self.reactor.callLater(3.5, self.send, "(7^.^)7")
        self.reactor.callLater(5.0, self.send, "(>^.^<)")

    @dangerousCommand
    def command_SHUTDOWN(self, args, **kwargs):
        """shutdown the buildbot master"""
        # FIXME: NEED TO THINK ABOUT!
        if args not in ('check', 'start', 'stop', 'now'):
            raise UsageError("Try '"+self.bot.commandPrefix+"shutdown check|start|stop|now'.")

        botmaster = self.master.botmaster
        shuttingDown = botmaster.shuttingDown

        if args == 'check':
            if shuttingDown:
                self.send("Status: buildbot is shutting down.")
            else:
                self.send("Status: buildbot is running.")
        elif args == 'start':
            if shuttingDown:
                self.send("Shutdown already started.")
            else:
                self.send("Starting clean shutdown.")
                botmaster.cleanShutdown()
        elif args == 'stop':
            if not shuttingDown:
                self.send("There is no ongoing shutdown to stop.")
            else:
                self.send("Stopping clean shutdown.")
                botmaster.cancelCleanShutdown()
        elif args == 'now':
            self.send("Stopping buildbot.")
            self.reactor.stop()
    command_SHUTDOWN.usage = {
        None: "shutdown check|start|stop|now - shutdown the buildbot master",
        "check": "shutdown check - check if the buildbot master is running or shutting down",
        "start": "shutdown start - start a clean shutdown",
        "stop": "shutdown cancel - stop the clean shutdown",
        "now": "shutdown now - shutdown immediately without waiting for the builders to finish"}


class StatusBot(service.AsyncMultiService):

    """ Abstract status bot """

    contactClass = Contact

    commandPrefix = ''
    commandSuffix = None

    def __init__(self, authz=None, tags=None, notify_events=None,
                 useRevisions=False, showBlameList=False,
                 categories=None  # deprecated
                 ):
        super().__init__()
        self.tags = tags or categories
        if notify_events is None:
            notify_events = {}
        self.notify_events = notify_events
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self.authz = self._expand_authz(authz)
        self.contacts = {}
        self.reported_builds = {}  # tuples (when, buildername, buildnum) for each channel/user

    @staticmethod
    def _expand_authz(authz):
        if authz is None:
            authz = {}
        expanded_authz = {}
        for cmds, val in authz.items():
            if not isinstance(cmds, (tuple, list)):
                cmds = cmds,
            for cmd in cmds:
                expanded_authz[cmd.upper()] = val
        return expanded_authz

    def getContact(self, user=None, channel=None):
        """ get a Contact instance for ``user`` on ``channel`` """
        try:
            return self.contacts[(channel, user)]
        except KeyError:
            new_contact = self.contactClass(self, user=user, channel=channel)
            self.contacts[(channel, user)] = new_contact
            new_contact.setServiceParent(self)
            return new_contact

    def _getObjectId(self):
        return self.master.db.state.getObjectId(
            self.nickname, '{0.__module__}.{0.__name__}'.format(self.__class__))

    @defer.inlineCallbacks
    def loadNotifyContacts(self):
        objectid = yield self._getObjectId()
        notify_contacts = yield self.master.db.state.getState(objectid, 'notify_contacts', None)
        if notify_contacts is not None:
            for user, channel, events in notify_contacts:
                contact = self.getContact(user, channel)
                try:
                    contact.add_notification_events(events)
                except UsageError:
                    pass

    @defer.inlineCallbacks
    def saveNotifyContacts(self):
        objectid = yield self._getObjectId()
        notify_contacts = [(contact.userid, contact.channelid, list(contact.notify_events))
                           for contact in self.contacts.values() if contact.userid is not None]
        yield self.master.db.state.setState(objectid, 'notify_contacts', notify_contacts)

    def startService(self):
        self.loadNotifyContacts()
        return super().startService()

    def send_message(self, channel, message):
        raise NotImplementedError()

    def log(self, msg):
        try:
            name = self.parent.name
        except AttributeError:
            name = self.__class__.__name__
        log.msg("{}: {}".format(name, msg))


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
