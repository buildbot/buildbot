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
from __future__ import print_function
from future.utils import string_types

import abc

from twisted.internet import defer

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import utils
from buildbot.reporters.message import MessageFormatter as DefaultMessageFormatter
from buildbot.reporters.message import MessageFormatterMissingWorker
from buildbot.util import service

ENCODING = 'utf-8'


class NotifierBase(service.BuildbotService):

    __meta__ = abc.ABCMeta

    possible_modes = ("change", "failing", "passing", "problem", "warnings",
                      "exception", "cancelled")

    def computeShortcutModes(self, mode):
        if isinstance(mode, string_types):
            if mode == "all":
                mode = ("failing", "passing", "warnings",
                        "exception", "cancelled")
            elif mode == "warnings":
                mode = ("failing", "warnings")
            else:
                mode = (mode,)
        return mode

    def checkConfig(self, mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    addLogs=False, addPatch=False,
                    name=None, schedulers=None, branches=None,
                    watchedWorkers=None, messageFormatterMissingWorker=None):

        for m in self.computeShortcutModes(mode):
            if m not in self.possible_modes:
                if m == "all":
                    config.error(
                        "mode 'all' is not valid in an iterator and must be passed in as a separate string")
                else:
                    config.error(
                        "mode %s is not a valid mode" % (m,))

        if name is None:
            self.name = self.__class__.__name__
            if tags is not None:
                self.name += "_tags_" + "+".join(tags)
            if builders is not None:
                self.name += "_builders_" + "+".join(builders)
            if schedulers is not None:
                self.name += "_schedulers_" + "+".join(schedulers)
            if branches is not None:
                self.name += "_branches_" + "+".join(branches)

        if '\n' in subject:
            config.error(
                'Newlines are not allowed in message subjects')

        # you should either limit on builders or tags, not both
        if builders is not None and tags is not None:
            config.error(
                "Please specify only builders or tags to include - " +
                "not both.")

        if not(watchedWorkers == 'all' or watchedWorkers is None or
               isinstance(watchedWorkers, (list, tuple, set))):
                    config.error("watchedWorkers must be 'all', None, or list of worker names")

    def reconfigService(self, mode=("failing", "passing", "warnings"),
                        tags=None, builders=None,
                        buildSetSummary=False, messageFormatter=None,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        addLogs=False, addPatch=False,
                        name=None, schedulers=None, branches=None,
                        watchedWorkers=None, messageFormatterMissingWorker=None):

        self.mode = self.computeShortcutModes(mode)
        self.tags = tags
        self.builders = builders
        self.schedulers = schedulers
        self.branches = branches
        self.subject = subject
        self.addLogs = addLogs
        self.addPatch = addPatch
        if messageFormatter is None:
            messageFormatter = DefaultMessageFormatter()
        self.messageFormatter = messageFormatter
        if messageFormatterMissingWorker is None:
            messageFormatterMissingWorker = MessageFormatterMissingWorker()
        self.messageFormatterMissingWorker = messageFormatterMissingWorker
        self.buildSetSummary = buildSetSummary
        self._buildset_complete_consumer = None
        if watchedWorkers is None:
            self.watchedWorkers = ()
        else:
            self.watchedWorkers = watchedWorkers

    @defer.inlineCallbacks
    def startService(self):
        yield service.BuildbotService.startService(self)
        startConsuming = self.master.mq.startConsuming
        self._buildsetCompleteConsumer = yield startConsuming(
            self.buildsetComplete,
            ('buildsets', None, 'complete'))
        self._buildCompleteConsumer = yield startConsuming(
            self.buildComplete,
            ('builds', None, 'finished'))
        self._workerMissingConsumer = yield startConsuming(
            self.workerMissing,
            ('workers', None, 'missing'))

    @defer.inlineCallbacks
    def stopService(self):
        yield service.BuildbotService.stopService(self)
        if self._buildsetCompleteConsumer is not None:
            yield self._buildsetCompleteConsumer.stopConsuming()
            self._buildsetCompleteConsumer = None
        if self._buildCompleteConsumer is not None:
            yield self._buildCompleteConsumer.stopConsuming()
            self._buildCompleteConsumer = None
        if self._workerMissingConsumer is not None:
            yield self._workerMissingConsumer.stopConsuming()
            self._workerMissingConsumer = None

    def wantPreviousBuild(self):
        return "change" in self.mode or "problem" in self.mode

    @defer.inlineCallbacks
    def buildsetComplete(self, key, msg):
        if not self.buildSetSummary:
            return
        bsid = msg['bsid']
        res = yield utils.getDetailsForBuildset(
            self.master, bsid,
            wantProperties=self.messageFormatter.wantProperties,
            wantSteps=self.messageFormatter.wantSteps,
            wantPreviousBuild=self.wantPreviousBuild(),
            wantLogs=self.messageFormatter.wantLogs)

        builds = res['builds']
        buildset = res['buildset']

        # only include builds for which isMessageNeeded returns true
        builds = [build for build in builds if self.isMessageNeeded(build)]
        if builds:
            self.buildMessage("whole buildset", builds, buildset['results'])

    @defer.inlineCallbacks
    def buildComplete(self, key, build):
        if self.buildSetSummary:
            return
        br = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        buildset = yield self.master.data.get(("buildsets", br['buildsetid']))
        yield utils.getDetailsForBuilds(
            self.master, buildset, [build],
            wantProperties=self.messageFormatter.wantProperties,
            wantSteps=self.messageFormatter.wantSteps,
            wantPreviousBuild=self.wantPreviousBuild(),
            wantLogs=self.messageFormatter.wantLogs)
        # only include builds for which isMessageNeeded returns true
        if self.isMessageNeeded(build):
            self.buildMessage(
                build['builder']['name'], [build], build['results'])

    def matchesAnyTag(self, tags):
        return self.tags and any(tag for tag in self.tags if tag in tags)

    def isMessageNeeded(self, build):
        # here is where we actually do something.
        builder = build['builder']
        scheduler = build['properties'].get('scheduler', [None])[0]
        branch = build['properties'].get('branch', [None])[0]
        results = build['results']
        if self.builders is not None and builder['name'] not in self.builders:
            return False  # ignore this build
        if self.schedulers is not None and scheduler not in self.schedulers:
            return False  # ignore this build
        if self.branches is not None and branch not in self.branches:
            return False  # ignore this build
        if self.tags is not None and \
                not self.matchesAnyTag(builder['tags']):
            return False  # ignore this build

        if "change" in self.mode:
            prev = build['prev_build']
            if prev and prev['results'] != results:
                return True
        if "failing" in self.mode and results == FAILURE:
            return True
        if "passing" in self.mode and results == SUCCESS:
            return True
        if "problem" in self.mode and results == FAILURE:
            prev = build['prev_build']
            if prev and prev['results'] != FAILURE:
                return True
        if "warnings" in self.mode and results == WARNINGS:
            return True
        if "exception" in self.mode and results == EXCEPTION:
            return True
        if "cancelled" in self.mode and results == CANCELLED:
            return True

        return False

    @defer.inlineCallbacks
    def getLogsForBuild(self, build):
        all_logs = []
        steps = yield self.master.data.get(('builds', build['buildid'], "steps"))
        for step in steps:
            logs = yield self.master.data.get(("steps", step['stepid'], 'logs'))
            for l in logs:
                l['stepname'] = step['name']
                l['content'] = yield self.master.data.get(("logs", l['logid'], 'contents'))
                all_logs.append(l)
        defer.returnValue(all_logs)

    @defer.inlineCallbacks
    def buildMessage(self, name, builds, results):
        patches = []
        logs = []
        body = ""
        subject = None
        msgtype = None
        users = set()
        for build in builds:
            if self.addPatch:
                ss_list = build['buildset']['sourcestamps']

                for ss in ss_list:
                    if 'patch' in ss and ss['patch'] is not None:
                        patches.append(ss['patch'])
            if self.addLogs:
                build_logs = yield self.getLogsForBuild(build)
                logs.extend(build_logs)

            if 'prev_build' in build and build['prev_build'] is not None:
                previous_results = build['prev_build']['results']
            else:
                previous_results = None
            blamelist = yield utils.getResponsibleUsersForBuild(self.master, build['buildid'])
            buildmsg = yield self.messageFormatter.formatMessageForBuildResults(
                self.mode, name, build['buildset'], build, self.master,
                previous_results, blamelist)
            users.update(set(blamelist))
            msgtype = buildmsg['type']
            body += buildmsg['body']
            if 'subject' in buildmsg:
                subject = buildmsg['subject']

        yield self.sendMessage(body, subject, msgtype, name, results, builds,
                               list(users), patches, logs)

    @abc.abstractmethod
    def sendMessage(self, body, subject=None, type=None, builderName=None,
                    results=None, builds=None, users=None, patches=None,
                    logs=None, worker=None):
        pass

    def isWorkerMessageNeeded(self, worker):
        return self.watchedWorkers == 'all' or worker['name'] in self.watchedWorkers

    @defer.inlineCallbacks
    def workerMissing(self, key, worker):
        if not self.isWorkerMessageNeeded(worker):
            return
        msg = yield self.messageFormatterMissingWorker.formatMessageForMissingWorker(self.master, worker)
        text = msg['body'].encode(ENCODING)
        if 'subject' in msg:
            subject = msg['subject']
        else:
            subject = "Buildbot worker {name} missing".format(**worker)
        assert msg['type'] in ('plain', 'html'), \
            "'%s' message type must be 'plain' or 'html'." % msg['type']

        yield self.sendMessage(text, subject, msg['type'], users=worker['notify'], worker=worker['name'])
