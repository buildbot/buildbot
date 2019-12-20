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

from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.python import log
from twisted.python import usage
from twisted.web import resource
from twisted.web import server

from buildbot import util
from buildbot import version
from buildbot.data import resultspec
from buildbot.plugins.db import get_plugins
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import statusToString
from buildbot.reporters import utils
from buildbot.util import service
from buildbot.util import unicode2bytes

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
        ["codebase", None, "", "which codebase to build"],
        ["branch", None, "master", "which branch to build"],
        ["revision", None, "HEAD", "which revision to build"],
        ["project", None, "", "which project to build"],
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
        raise ValueError('@dangerousCommand can be used only for commands')
    dangerous_commands.append(command[8:])
    return method


class Channel(service.AsyncService):
    """
    This class holds what should be shared between users on a single channel.
    In particular it is responsible for maintaining notification states and
    send notifications.
    """

    def __init__(self, bot, channel):
        self.name = "Channel({})".format(channel)
        self.id = channel
        self.bot = bot
        self.notify_events = set()
        self.subscribed = []
        self.build_subscriptions = []
        self.reported_builds = []  # tuples (when, buildername, buildnum)
        self.missing_workers = set()
        self.useRevisions = bot.useRevisions

    def send(self, message, **kwargs):
        return self.bot.send_message(self.id, message, **kwargs)

    def stopService(self):
        if self.subscribed:
            self.unsubscribe_from_build_events()

    def validate_notification_event(self, event):
        if not re.compile("^(started|finished|success|warnings|failure|exception|"
                          "cancelled|problem|recovery|worse|better|worker|"
                          # this is deprecated list
                          "(success|warnings|failure|exception)To"
                          "(Success|Warnings|Failure|Exception))$").match(event):
            raise UsageError("Try '" + self.bot.commandPrefix + "notify on|off _EVENT_'.")

    @defer.inlineCallbacks
    def list_notified_events(self):
        if self.notify_events:
            yield self.send("The following events are being notified: {}."
                            .format(", ".join(sorted(self.notify_events))))
        else:
            yield self.send("No events are being notified.")

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

        def workerEvent(key, msg):
            if key[2] == 'missing':
                return self.workerMissing(msg)
            if key[2] == 'connected':
                return self.workerConnected(msg)

        for e, f in (("new", buildStarted),             # BuilderStarted
                     ("finished", buildFinished)):      # BuilderFinished
            handle = yield startConsuming(f, ('builders', None, 'builds', None, e))
            self.subscribed.append(handle)

        handle = yield startConsuming(workerEvent, ('workers', None, None))
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

    @defer.inlineCallbacks
    def buildStarted(self, build):
        builder = yield self.bot.getBuilder(builderid=build['builderid'])
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

        self.send(r + ".")

    @defer.inlineCallbacks
    def buildFinished(self, build, watched=False):
        builder = yield self.bot.getBuilder(builderid=build['builderid'])
        builderName = builder['name']
        buildNumber = build['number']

        # only notify about builders we are interested in
        if (self.bot.tags is not None and
                not self.bot.builderMatchesAnyTag(builder.get('tags', []))):
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
                .format(builderName, ','.join(revisions), self.bot.format_build_status(build))
        else:
            r = "Build [#{:d}]({}) of `{}` {}" \
                .format(buildNumber, url, builderName, self.bot.format_build_status(build))

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

        if result in self.bot.results_severity and \
                (self.notify_for('better', 'worse', 'problem', 'recovery') or
                 any('To' in e for e in self.notify_events)):
            prev_build = yield self.master.data.get(
                ('builders', build['builderid'], 'builds', build['number'] - 1))
            if prev_build:
                prev_result = prev_build['results']

                if prev_result in self.bot.results_severity:
                    result_severity = self.bot.results_severity.index(result)
                    prev_result_severity = self.bot.results_severity.index(prev_result)
                    if self.notify_for('better') and \
                            result_severity < prev_result_severity:
                        return True
                    if self.notify_for('worse') and \
                            result_severity > prev_result_severity:
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

    def workerMissing(self, worker):
        self.missing_workers.add(worker['workerid'])
        if self.notify_for('worker'):
            self.send("Worker `{name}` is missing. It was seen last on {last_connection}.".format(**worker))
        self.bot.saveMissingWorkers()

    def workerConnected(self, worker):
        workerid = worker['workerid']
        if workerid in self.missing_workers:
            self.missing_workers.remove(workerid)
            if self.notify_for('worker'):
                self.send("Worker `{name}` is back online.".format(**worker))
            self.bot.saveMissingWorkers()


class Contact:
    """I hold the state for a single user's interaction with the buildbot.

    There will be one instance of me for each user who interacts personally
    with the buildbot. There will be an additional instance for each
    'broadcast contact' (chat rooms, IRC channels as a whole).
    """

    def __init__(self, user, channel):
        """
        :param StatusBot bot: StatusBot this Contact belongs to
        :param user: User ID representing this contact
        :param channel: Channel this contact is on
        """
        self.user_id = user
        self.channel = channel

    @property
    def bot(self):
        return self.channel.bot

    @property
    def master(self):
        return self.channel.bot.master

    @property
    def is_private_chat(self):
        return self.user_id == self.channel.id

    @staticmethod
    def overrideCommand(meth):
        try:
            base_meth = getattr(Contact, meth.__name__)
        except AttributeError:
            pass
        else:
            try:
                meth.__doc__ = base_meth.__doc__
            except AttributeError:
                pass
            try:
                meth.usage = base_meth.usage
            except AttributeError:
                pass
        return meth

    # Communication with the user

    def send(self, message, **kwargs):
        return self.channel.send(message, **kwargs)

    def access_denied(self, *args, **kwargs):
        return self.send("Thou shall not pass, {}!!!".format(self.user_id))

    # Main dispatchers for incoming messages

    def getCommandMethod(self, command):
        command = command.upper()
        try:
            method = getattr(self, 'command_' + command)
        except AttributeError:
            return None
        get_authz = self.bot.authz.get
        acl = get_authz(command)
        if acl is None:
            if command in dangerous_commands:
                acl = get_authz('!', False)
            else:
                acl = get_authz('', True)
            acl = get_authz('*', acl)
        if isinstance(acl, (list, tuple)):
            acl = self.user_id in acl
        elif acl not in (True, False, None):
            acl = self.user_id == acl
        if not acl:
            return self.access_denied
        return method

    @defer.inlineCallbacks
    def handleMessage(self, message, **kwargs):
        message = message.lstrip()
        parts = message.split(' ', 1)
        if len(parts) == 1:
            parts = parts + ['']
        cmd, args = parts

        cmd_suffix = self.bot.commandSuffix
        if cmd_suffix and cmd.endswith(cmd_suffix):
            cmd = cmd[:-len(cmd_suffix)]

        self.bot.log("Received command `{}` from {}".format(cmd, self.describeUser()))

        if cmd.startswith(self.bot.commandPrefix):
            meth = self.getCommandMethod(cmd[len(self.bot.commandPrefix):])
        else:
            meth = None

        if not meth:
            if message[-1] == '!':
                self.send("What you say!")
                return
            elif cmd.startswith(self.bot.commandPrefix):
                self.send("I don't get this '{}'...".format(cmd))
                meth = self.command_COMMANDS
            else:
                if self.is_private_chat:
                    self.send("Say what?")
                return

        try:
            result = yield meth(args.strip(), **kwargs)
        except UsageError as e:
            self.send(str(e))
            return
        except Exception as e:
            self.bot.log_err(e)
            self.send("Something bad happened (see logs)")
            return
        return result

    def splitArgs(self, args):
        """Returns list of arguments parsed by shlex.split() or
        raise UsageError if failed"""
        try:
            return shlex.split(args)
        except ValueError as e:
            raise UsageError(e)

    def command_HELLO(self, args, **kwargs):
        """say hello"""
        self.send(random.choice(GREETINGS))

    def command_VERSION(self, args, **kwargs):
        """show buildbot version"""
        self.send("This is buildbot-{} at your service".format(version))

    @defer.inlineCallbacks
    def command_LIST(self, args, **kwargs):
        """list configured builders or workers"""
        args = self.splitArgs(args)

        all = False
        num = 10
        try:
            num = int(args[0])
            del args[0]
        except ValueError:
            if args[0] == 'all':
                all = True
                del args[0]
        except IndexError:
            pass

        if not args:
            raise UsageError("Try '" + self.bot.commandPrefix + "list [all|N] builders|workers|changes'.")

        if args[0] == 'builders':
            bdicts = yield self.bot.getAllBuilders()
            online_builderids = yield self.bot.getOnlineBuilders()

            response = ["I found the following builders:"]
            for bdict in bdicts:
                if bdict['builderid'] in online_builderids:
                    response.append(bdict['name'])
                elif all:
                    response.append(bdict['name'])
                    response.append("[offline]")
            self.send(' '.join(response))

        elif args[0] == 'workers':
            workers = yield self.master.data.get(('workers',))

            response = ["I found the following workers:"]
            for worker in workers:
                if worker['configured_on']:
                    response.append(worker['name'])
                    if not worker['connected_to']:
                        response.append("[disconnected]")
                elif all:
                    response.append(worker['name'])
                    response.append("[offline]")
            self.send(' '.join(response))
            return

        elif args[0] == 'changes':
            if all:
                self.send("Do you really want me to list all changes? It can be thousands!\n"
                          "If you want to be flooded, specify the maximum number of changes to show.\n"
                          "Right now, I will show up to 100 recent changes.")
                num = 100

            changes = yield self.master.db.changes.getRecentChanges(num)

            response = ["I found the following recent changes:"]
            for change in reversed(changes):
                change['comment'] = change['comments'].split('\n')[0]
                change['date'] = change['when_timestamp'].strftime('%Y-%m-%d %H:%M')
                response.append(
                    "{comment})\n"
                    "Author: {author}\n"
                    "Date: {date}\n"
                    "Repository: {repository}\n"
                    "Branch: {branch}\n"
                    "Revision: {revision}\n".format(**change))
            self.send('\n\n'.join(response))

    command_LIST.usage = "list [all|N] builders|workers|changes - " \
                         "list configured builders, workers, or N recent changes"

    @defer.inlineCallbacks
    def command_STATUS(self, args, **kwargs):
        """list status of a builder (or all builders)"""
        args = self.splitArgs(args)
        if not args:
            which = ""
        elif len(args) == 1:
            which = args[0]
        else:
            raise UsageError("Try '" + self.bot.commandPrefix + "status _builder_'.")
        response = []
        if which == "":
            builders = yield self.bot.getAllBuilders()
            online_builderids = yield self.bot.getOnlineBuilders()
            for builder in builders:
                if builder['builderid'] in online_builderids:
                    status = yield self.bot.getBuildStatus(builder['name'], short=True)
                    response.append(status)
        elif which == "all":
            builders = yield self.bot.getAllBuilders()
            for builder in builders:
                status = yield self.bot.getBuildStatus(builder['name'], short=True)
                response.append(status)
        else:
            status = yield self.bot.getBuildStatus(which)
            response.append(status)
        if response:
            self.send('\n'.join(response))
    command_STATUS.usage = "status [_which_] - list status of a builder (or all builders)"

    @defer.inlineCallbacks
    def command_NOTIFY(self, args, **kwargs):
        """notify me about build events"""
        args = self.splitArgs(args)

        if not args:
            raise UsageError("Try '" + self.bot.commandPrefix + "notify on|off|list [_EVENT_]'.")
        action = args.pop(0)
        events = args

        if action in ("on", "on-quiet"):
            if not events:
                events = ('started', 'finished')
            self.channel.add_notification_events(events)

            if action == "on":
                yield self.channel.list_notified_events()
            self.bot.saveNotifyEvents()

        elif action in ("off", "off-quiet"):
            if events:
                self.channel.remove_notification_events(events)
            else:
                self.channel.remove_all_notification_events()

            if action == "off":
                yield self.channel.list_notified_events()
            self.bot.saveNotifyEvents()

        elif action == "list":
            yield self.channel.list_notified_events()

        else:
            raise UsageError("Try '" + self.bot.commandPrefix + "notify on|off|list [_EVENT_]'.")

    command_NOTIFY.usage = ("notify on|off|list [_EVENT_] ... - notify me about build events;"
                            "  event should be one or more of: 'started', 'finished', 'failure',"
                            " 'success', 'exception', 'problem', 'recovery', 'better', or 'worse'")

    @defer.inlineCallbacks
    def command_WATCH(self, args, **kwargs):
        """announce the completion of an active build"""
        args = self.splitArgs(args)
        if len(args) != 1:
            raise UsageError("Try '" + self.bot.commandPrefix + "watch _builder_'.")

        which = args[0]
        builder = yield self.bot.getBuilder(buildername=which)

        # Get current builds on this builder.
        builds = yield self.bot.getRunningBuilds(builder['builderid'])
        if not builds:
            self.send("There are no currently running builds.")
            return

        def watchForCompleteEvent(key, msg):
            if key[-1] in ('finished', 'complete'):
                return self.channel.buildFinished(msg, watched=True)

        for build in builds:
            startConsuming = self.master.mq.startConsuming
            handle = yield startConsuming(
                watchForCompleteEvent,
                ('builds', str(build['buildid']), None))
            self.channel.build_subscriptions.append((build['buildid'], handle))

            url = utils.getURLForBuild(self.master, builder['builderid'], build['number'])

            if self.bot.useRevisions:
                revisions = yield self.bot.getRevisionsForBuild(build)
                r = "Watching build on `{}` containing revision(s) {} until it finishes..." \
                    .format(which, ','.join(revisions))
            else:
                r = "Watching build [#{:d}]({}) of `{}` until it finishes..." \
                    .format(build['number'], url, which)

            self.send(r)
    command_WATCH.usage = "watch _which_ - announce the completion of an active build"

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
        builder = yield self.bot.getBuilder(buildername=builderName)
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
            self.bot.log("Force: bad branch '{}'".format(branch))
            self.send("Sorry, bad branch '{}'".format(branch))
            return
        if revision and not revision_validate.match(revision):
            self.bot.log("Force: bad revision '{}'".format(revision))
            self.send("Sorry, bad revision '{}'".format(revision))
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
                    self.bot.log("Force: bad property name='{}', value='{}'"
                                 .format(pname, pvalue))
                    self.send("Sorry, bad property name='{}', value='{}'"
                              .format(pname, pvalue))
                    return
                properties.setProperty(pname, pvalue, "Force Build Chat")

        properties.setProperty("reason", reason, "Force Build Chat")
        properties.setProperty("owner", self.describeUser(), "Force Build Chat")

        reason = "forced: by {}: {}".format(self.describeUser(), reason)
        try:
            yield self.master.data.updates.addBuildset(builderids=[builder['builderid']],
                                                       # For now, we just use
                                                       # this as the id.
                                                       scheduler="status.words",
                                                       sourcestamps=[{
                                                           'codebase': codebase, 'branch': branch,
                                                           'revision': revision, 'project': project,
                                                           'repository': ""}],
                                                       reason=reason,
                                                       properties=properties.asDict(),
                                                       waited_for=False)
        except AssertionError as e:
            self.send("I can't: " + str(e))
        else:
            self.send("Force build successfully requested.")

    command_FORCE.usage = ("force build [--codebase=CODEBASE] [--branch=branch] [--revision=revision]"
                           " [--props=prop1=val1,prop2=val2...] _which_ _reason_ - Force a build")

    @defer.inlineCallbacks
    @dangerousCommand
    def command_STOP(self, args, **kwargs):
        """stop a running build"""
        args = self.splitArgs(args)
        if len(args) < 3 or args[0] != 'build':
            raise UsageError("Try '" + self.bot.commandPrefix + "stop build _which_ _reason_'.")
        which = args[1]
        reason = ' '.join(args[2:])

        r = "stopped: by {}: {}".format(self.describeUser(), reason)

        # find an in-progress build
        builder = yield self.bot.getBuilder(buildername=which)
        builderid = builder['builderid']
        builds = yield self.bot.getRunningBuilds(builderid)

        if not builds:
            self.send("Sorry, no build is currently running.")
            return

        for bdict in builds:
            num = bdict['number']

            yield self.master.data.control('stop', {'reason': r},
                                           ('builders', builderid, 'builds', num))
            if self.bot.useRevisions:
                revisions = yield self.bot.getRevisionsForBuild(bdict)
                response = "Build containing revision(s) {} interrupted".format(','.join(
                    revisions))
            else:
                url = utils.getURLForBuild(self.master, builderid, num)
                response = "Build [#{:d}]({}) of `{}` interrupted.".format(num, url, which)
            self.send(response)

    command_STOP.usage = "stop build _which_ _reason_ - Stop a running build"

    @defer.inlineCallbacks
    def command_LAST(self, args, **kwargs):
        """list last build status for a builder"""
        # FIXME: NEED TO THINK ABOUT!
        args = self.splitArgs(args)

        if not args:
            builders = yield self.bot.getAllBuilders()
            online_builderids = yield self.bot.getOnlineBuilders()
            builders = [b for b in builders if b['builderid'] in online_builderids]
        elif len(args) == 1:
            arg = args[0]
            if arg == 'all':
                builders = yield self.bot.getAllBuilders()
            else:
                builder = yield self.bot.getBuilder(buildername=arg)
                if not builder:
                    raise UsageError("no such builder")
                builders = [builder]
        else:
            raise UsageError("Try '" + self.bot.commandPrefix + "last _builder_'.")

        messages = []

        for builder in builders:
            lastBuild = yield self.bot.getLastCompletedBuild(builder['builderid'])
            if not lastBuild:
                status = "no builds run since last restart"
            else:
                complete_at = lastBuild['complete_at']
                if complete_at:
                    complete_at = util.datetime2epoch(complete_at)
                    ago = util.fuzzyInterval(int(reactor.seconds() -
                                                 complete_at))
                else:
                    ago = "??"
                status = self.bot.format_build_status(lastBuild)
                status = 'last build {} ({} ago)'.format(status, ago)
                if lastBuild['results'] != SUCCESS:
                    status += ': {}'.format(lastBuild['state_string'])
            messages.append("`{}`: {}".format(builder['name'], status))
        if messages:
            self.send('\n'.join(messages))

    command_LAST.usage = "last [_which_] - list last build status for builder _which_"

    @classmethod
    def build_commands(cls):
        commands = []
        for k in dir(cls):
            if k.startswith('command_'):
                commands.append(k[8:].lower())
        commands.sort()
        return commands

    def describeUser(self):
        if self.is_private_chat:
            return self.user_id
        return "{} on {}".format(self.user_id, self.channel.id)

    # commands

    def command_HELP(self, args, **kwargs):
        """give help for a command or one of it's arguments"""
        args = self.splitArgs(args)
        if not args:
            commands = self.build_commands()
            response = []
            for command in commands:
                meth = getattr(self, 'command_' + command.upper())
                doc = getattr(meth, '__doc__', None)
                if doc:
                    response.append("{} - {}".format(command, doc))
            if response:
                self.send('\n'.join(response))
            return
        command = args[0]
        if command.startswith(self.bot.commandPrefix):
            command = command[len(self.bot.commandPrefix):]
        meth = getattr(self, 'command_' + command.upper(), None)
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
        elif callable(doc):
            try:
                doc = doc(*args[1:])
            except (TypeError, ValueError):
                doc = None
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
        str = "Buildbot commands: " + ", ".join(self.bot.commandPrefix + c for c in commands)
        self.send(str)
    command_COMMANDS.usage = "commands - List available commands"

    @dangerousCommand
    def command_SHUTDOWN(self, args, **kwargs):
        """shutdown the buildbot master"""
        # FIXME: NEED TO THINK ABOUT!
        if args not in ('check', 'start', 'stop', 'now'):
            raise UsageError("Try '" + self.bot.commandPrefix + "shutdown check|start|stop|now'.")

        botmaster = self.channel.master.botmaster
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
            reactor.stop()
    command_SHUTDOWN.usage = {
        None: "shutdown check|start|stop|now - shutdown the buildbot master",
        "check": "shutdown check - check if the buildbot master is running or shutting down",
        "start": "shutdown start - start a clean shutdown",
        "stop": "shutdown cancel - stop the clean shutdown",
        "now": "shutdown now - shutdown immediately without waiting for the builders to finish"}


class StatusBot(service.AsyncMultiService):
    """ Abstract status bot """

    contactClass = Contact
    channelClass = Channel

    commandPrefix = ''
    commandSuffix = None

    offline_string = "offline"
    idle_string = "idle"
    running_string = "running:"

    def __init__(self, authz=None, tags=None, notify_events=None,
                 useRevisions=False, showBlameList=False):
        super().__init__()
        self.tags = tags
        if notify_events is None:
            notify_events = {}
        self.notify_events = notify_events
        self.useRevisions = useRevisions
        self.showBlameList = showBlameList
        self.authz = self.expand_authz(authz)
        self.contacts = {}
        self.channels = {}

    @staticmethod
    def expand_authz(authz):
        if authz is None:
            authz = {}
        expanded_authz = {}
        for cmds, val in authz.items():
            if not isinstance(cmds, (tuple, list)):
                cmds = (cmds,)
            for cmd in cmds:
                expanded_authz[cmd.upper()] = val
        return expanded_authz

    def isValidUser(self, user):
        for auth in self.authz.values():
            if auth is True \
                    or (isinstance(auth, (list, tuple)) and user in auth)\
                    or user == auth:
                return True
        # If user is in '', we have already returned; otherwise check if defaults apply
        return '' not in self.authz

    def getContact(self, user, channel):
        """ get a Contact instance for ``user`` on ``channel`` """
        try:
            return self.contacts[(channel, user)]
        except KeyError:
            valid = self.isValidUser(user)
            new_contact = self.contactClass(user=user,
                                            channel=self.getChannel(channel, valid))
            if valid:
                self.contacts[(channel, user)] = new_contact
            return new_contact

    def getChannel(self, channel, valid=True):
        try:
            return self.channels[channel]
        except KeyError:
            new_channel = self.channelClass(self, channel)
            if valid:
                self.channels[channel] = new_channel
                new_channel.setServiceParent(self)
            return new_channel

    def _get_object_id(self):
        return self.master.db.state.getObjectId(
            self.nickname, '{0.__module__}.{0.__name__}'.format(self.__class__))

    @defer.inlineCallbacks
    def _save_channels_state(self, attr, json_type=None):
        if json_type is None:
            json_type = lambda x: x
        data = [(k, v) for k, v in ((channel.id, json_type(getattr(channel, attr)))
                                    for channel in self.channels.values()) if v]
        try:
            objectid = yield self._get_object_id()
            yield self.master.db.state.setState(objectid, attr, data)
        except Exception as err:
            self.log_err(err, "saveState '{}'".format(attr))

    @defer.inlineCallbacks
    def _load_channels_state(self, attr, setter):
        try:
            objectid = yield self._get_object_id()
            data = yield self.master.db.state.getState(objectid, attr, ())
        except Exception as err:
            self.log_err(err, "loadState ({})".format(attr))
        else:
            if data is not None:
                for c, d in data:
                    try:
                        setter(self.getChannel(c), d)
                    except Exception as err:
                        self.log_err(err, "loadState '{}' ({})".format(attr, c))

    @defer.inlineCallbacks
    def loadState(self):
        yield self._load_channels_state('notify_events', lambda c, e: c.add_notification_events(e))
        yield self._load_channels_state('missing_workers', lambda c, w: c.missing_workers.update(w))

    @defer.inlineCallbacks
    def saveNotifyEvents(self):
        yield self._save_channels_state('notify_events', list)

    @defer.inlineCallbacks
    def saveMissingWorkers(self):
        yield self._save_channels_state('missing_workers', list)

    def send_message(self, chat, message, **kwargs):
        raise NotImplementedError()

    def _get_log_system(self, source):
        if source is None:
            source = self.__class__.__name__
        try:
            parent = self.parent.name
        except AttributeError:
            parent = '-'
        name = "{},{}".format(parent, source)
        return name

    def log(self, msg, source=None):
        log.callWithContext({"system": self._get_log_system(source)}, log.msg, msg)

    def log_err(self, error=None, why=None, source=None):
        log.callWithContext({"system": (self._get_log_system(source))}, log.err, error, why)

    def builderMatchesAnyTag(self, builder_tags):
        return any(tag for tag in builder_tags if tag in self.tags)

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

    def getCurrentBuildstep(self, build):
        d = self.master.data.get(('builds', build['buildid'], 'steps'),
                                 filters=[
                                     resultspec.Filter('complete', 'eq', [False])],
                                 order=['number'],
                                 limit=1)
        return d

    @defer.inlineCallbacks
    def getBuildStatus(self, which, short=False):
        response = '`{}`: '.format(which)

        builder = yield self.getBuilder(buildername=which)
        builderid = builder['builderid']
        runningBuilds = yield self.getRunningBuilds(builderid)

        # pylint: disable=too-many-nested-blocks
        if not runningBuilds:
            onlineBuilders = yield self.getOnlineBuilders()
            if builderid in onlineBuilders:
                response += self.idle_string
                lastBuild = yield self.getLastCompletedBuild(builderid)
                if lastBuild:
                    complete_at = lastBuild['complete_at']
                    if complete_at:
                        complete_at = util.datetime2epoch(complete_at)
                        ago = util.fuzzyInterval(int(reactor.seconds() -
                                                     complete_at))
                    else:
                        ago = "??"
                    status = self.format_build_status(lastBuild, short=short)
                    if not short:
                        status = ", " + status
                        if lastBuild['results'] != SUCCESS:
                            status_string = lastBuild.get('status_string')
                            if status_string:
                                status += ": " + status_string
                    response += '  last build {} ago{}'.format(ago, status)
            else:
                response += self.offline_string
        else:
            response += self.running_string
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

    results_descriptions = {
        SKIPPED: "was skipped",
        SUCCESS: "completed successfully",
        WARNINGS: "completed with warnings",
        FAILURE: "failed",
        EXCEPTION: "stopped with exception",
        RETRY: "has been retried",
        CANCELLED: "was cancelled",
    }

    results_severity = (
        SKIPPED, SUCCESS, WARNINGS, FAILURE, CANCELLED, EXCEPTION
    )

    def format_build_status(self, build, short=False):
        """ Optionally add color to the message """
        return self.results_descriptions[build['results']]


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


class WebhookResource(resource.Resource, service.AsyncService):
    """
    This is a service be used by chat bots based on web-hooks.
    It automatically sets and deletes the resource and calls ``process_webhook``
    method of its parent.
    """

    def __init__(self, path):
        resource.Resource.__init__(self)
        www = get_plugins('www', None, load_now=True)
        if 'base' not in www:
            raise RuntimeError("could not find buildbot-www; is it installed?")
        self._root = www.get('base').resource
        self.path = path

    def startService(self):
        self._root.putChild(unicode2bytes(self.path), self)
        try:
            super().startService()
        except AttributeError:
            pass

    def stopService(self):
        try:
            super().stopService()
        except AttributeError:
            pass
        self._root.delEntity(unicode2bytes(self.path))

    def render_GET(self, request):
        return self.render_POST(request)

    def render_POST(self, request):
        try:
            d = self.parent.process_webhook(request)
        except Exception:
            d = defer.fail()

        def ok(_):
            request.setResponseCode(202)
            request.finish()

        def err(error):
            try:
                self.parent.log_err(error, "processing telegram request", self.__class__.__name__)
            except AttributeError:
                log.err(error, "processing telegram request")
            request.setResponseCode(500)
            request.finish()

        d.addCallbacks(ok, err)

        return server.NOT_DONE_YET
