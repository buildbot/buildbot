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
from future.utils import iteritems
from future.utils import string_types

from twisted.internet import defer
from twisted.python import log as twlog

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.reporters import utils
from buildbot.reporters.message import MessageFormatter as DefaultMessageFormatter
from buildbot.reporters.message import MessageFormatterMissingWorker
from buildbot.util import httpclientservice
from buildbot.util import service

ENCODING = 'utf8'

VALID_PARAMS = set(("sound", "callback", "timestamp",
                    "url", "url_title", "device",
                    "retry", "expire", "html"))


class PushoverNotifier(service.BuildbotService):

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

    def checkConfig(self, user_key, api_token,
                    mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    name=None, schedulers=None, branches=None,
                    priorities=None, otherParams=None,
                    watchedWorkers=None, messageFormatterMissingWorker=None):

        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

        for m in self.computeShortcutModes(mode):
            if m not in self.possible_modes:
                if m == "all":
                    config.error(
                        "mode 'all' is not valid in an iterator and must be passed in as a separate string")
                else:
                    config.error(
                        "mode %s is not a valid mode" % (m,))

        if name is None:
            self.name = "PushoverNotifier"
            if tags is not None:
                self.name += "_tags_" + "+".join(tags)
            if builders is not None:
                self.name += "_builders_" + "+".join(builders)
            if schedulers is not None:
                self.name += "_schedulers_" + "+".join(schedulers)
            if branches is not None:
                self.name += "_branches_" + "+".join(branches)

        if otherParams is not None and set(otherParams.keys()) - VALID_PARAMS:
            config.error("otherParams can be only 'sound', 'callback', 'timestamp', "
                         "'url', 'url_title', 'device', "
                         "'retry', 'expire', or 'html'")

        if '\n' in subject:
            config.error(
                'Newlines are not allowed in message subjects')

        # you should either limit on builders or tags, not both
        if builders is not None and tags is not None:
            config.error(
                "Please specify only builders or tags to include - " +
                "not both.")

    @defer.inlineCallbacks
    def reconfigService(self, user_key, api_token,
                        mode=("failing", "passing", "warnings"),
                        tags=None, builders=None,
                        buildSetSummary=False, messageFormatter=None,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        name=None, schedulers=None, branches=None,
                        priorities=None, otherParams=None,
                        watchedWorkers=None, messageFormatterMissingWorker=None
                       ):

        self.user_key = user_key
        self.api_token = api_token
        self.mode = self.computeShortcutModes(mode)
        self.tags = tags
        self.builders = builders
        self.schedulers = schedulers
        self.branches = branches
        self.subject = subject
        if messageFormatter is None:
            messageFormatter = DefaultMessageFormatter(template_type='html',
                template='The Buildbot has detected a <a href="{{ build_url }}">'
                         '{{ status_detected }}</a> of <i>{{ buildername }}</i> '
                         'while building {{ projects }} on {{ workername }}.'
            )
        self.messageFormatter = messageFormatter
        if messageFormatterMissingWorker is None:
            messageFormatterMissingWorker = MessageFormatterMissingWorker(
                template="The Buildbot working for '{{buildbot_title}}' "
                         "has noticed that the worker named {{worker.name}} "
                         "went away.\n\n"
                         "It last disconnected at {{worker.last_connection}}."
                )
        self.messageFormatterMissingWorker = messageFormatterMissingWorker
        self.buildSetSummary = buildSetSummary
        if priorities is None:
            self.priorities = {}
        else:
            self.priorities = priorities
        if watchedWorkers is None:
            self.watchedWorkers = []
        else:
            self.watchedWorkers = watchedWorkers
        if otherParams is None:
            self.otherParams = {}
        else:
            self.otherParams = otherParams
        self._buildset_complete_consumer = None
        self.watched = []

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, 'https://api.pushover.net')

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
            ('worker', None, 'missing'))

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
    def buildMessage(self, name, builds, results):
        patches = []
        logs = []
        msg = {'message': ""}
        for build in builds:
            if 'prev_build' in build and build['prev_build'] is not None:
                previous_results = build['prev_build']['results']
            else:
                previous_results = None
            blamelist = yield utils.getResponsibleUsersForBuild(self.master, build['buildid'])
            msgdict = yield self.messageFormatter.formatMessageForBuildResults(
                self.mode, name, build['buildset'], build, self.master,
                previous_results, blamelist)
            assert msgdict['type'] in ('plain', 'html'), \
                "'%s' message type must be 'plain' or 'html'." % msgdict['type']
            if msgdict['type'] == 'html':
                msg['html'] = '1'
            msg['message'] += msgdict['body']
            try:
                msg['priority'] = self.priorities[{
                    CANCELLED: 'cancelled',
                    EXCEPTION: 'exception',
                    FAILURE: 'failing',
                    SUCCESS: 'passing',
                    WARNINGS: 'warnings'}[build['results']]]
            except KeyError:
                pass
            if 'subject' in msgdict:
                msg['title'] = msgdict['subject']
            else:
                msg['title'] = self.subject % {'result': Results[results],
                                               'projectName': self.master.config.title,
                                               'title': self.master.config.title,
                                               'builder': name}
        self.sendMessage(msg)

    def sendMessage(self, params):
        twlog.msg("sending pushover notification")
        params.update(dict(user=self.user_key, token=self.api_token))
        params.update(self.otherParams)
        return self._http.post('/1/messages.json', params=params)

    @defer.inlineCallbacks
    def workerMissing(self, key, worker):
        if worker['name'] not in self.watchedWorkers:
            return
        msg = {'message': ""}
        msgdict = yield self.messageFormatterMissingWorker.formatMessageForMissingWorker(self.master, worker)
        text = msgdict['body'].encode(ENCODING)
        if 'subject' in msgdict:
            title = msgdict['subject']
        else:
            title = "Buildbot worker {name} missing".format(**worker)
        assert msgdict['type'] in ('plain', 'html'), \
            "'%s' message type must be 'plain' or 'html'." % msgdict['type']
        if msgdict['type'] == 'html':
            msg['html'] = 1
        msg['message'] += msgdict['body']
        priority = self.priorities.get('worker_missing', 0)
       
        self.sendMessage({'message': text, 'title': title, 'priority': priority})
