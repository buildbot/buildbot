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

import abc

from twisted.internet import defer

from buildbot import config
from buildbot.reporters import utils
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.generators.buildset import BuildSetStatusGenerator
from buildbot.reporters.generators.worker import WorkerMissingGenerator
from buildbot.util import service

ENCODING = 'utf-8'


class NotifierBase(service.BuildbotService):
    name = None
    __meta__ = abc.ABCMeta

    compare_attrs = ['generators']

    def computeShortcutModes(self, mode):
        if isinstance(mode, str):
            if mode == "all":
                mode = ("failing", "passing", "warnings",
                        "exception", "cancelled")
            elif mode == "warnings":
                mode = ("failing", "warnings")
            else:
                mode = (mode,)
        return mode

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generators = None
        self._buildsetCompleteConsumer = None
        self._buildCompleteConsumer = None
        self._workerMissingConsumer = None

    def checkConfig(self, mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    addLogs=False, addPatch=False,
                    schedulers=None, branches=None,
                    watchedWorkers=None, messageFormatterMissingWorker=None,
                    generators=None
                    ):

        # FIXME: TODO: maybe throw deprecation messages for non generator arguments
        has_old_arg = tags is not None or builders is not None or buildSetSummary or \
                      messageFormatter is not None or \
                      subject != "Buildbot %(result)s in %(title)s on %(builder)s" or \
                      addLogs or addPatch or schedulers is not None or \
                      branches is not None or watchedWorkers is not None or \
                      messageFormatterMissingWorker is not None
        if has_old_arg and generators is not None:
            config.error("can't specify generators and deprecated notifier arguments at the "
                         "same time")

        if generators is None:
            generators = self.create_generators_from_old_args(mode, tags, builders, buildSetSummary,
                                                              messageFormatter, subject, addLogs,
                                                              addPatch, schedulers,
                                                              branches, watchedWorkers,
                                                              messageFormatterMissingWorker)

        for g in generators:
            g.check()

        if self.name is None:
            self.name = self.__class__.__name__
            for g in generators:
                self.name += "_" + g.generate_name()

    @defer.inlineCallbacks
    def reconfigService(self, mode=("failing", "passing", "warnings"),
                        tags=None, builders=None,
                        buildSetSummary=False, messageFormatter=None,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        addLogs=False, addPatch=False,
                        schedulers=None, branches=None,
                        watchedWorkers=None, messageFormatterMissingWorker=None,
                        generators=None):

        if generators is None:
            generators = self.create_generators_from_old_args(mode, tags, builders, buildSetSummary,
                                                              messageFormatter, subject, addLogs,
                                                              addPatch, schedulers,
                                                              branches, watchedWorkers,
                                                              messageFormatterMissingWorker)

        self.generators = generators

        startConsuming = self.master.mq.startConsuming

        needs_buildsets_complete = any(isinstance(g, BuildSetStatusGenerator) for g in generators)
        needs_build_finished = any(isinstance(g, BuildStatusGenerator) for g in generators)
        needs_worker_missing = any(isinstance(g, WorkerMissingGenerator) for g in generators)

        if not needs_buildsets_complete and self._buildsetCompleteConsumer is not None:
            yield self._buildsetCompleteConsumer.stopConsuming()
            self._buildsetCompleteConsumer = None

        if needs_buildsets_complete and self._buildsetCompleteConsumer is None:
            self._buildsetCompleteConsumer = yield startConsuming(self.buildsetComplete,
                                                                  ('buildsets', None, 'complete'))

        if not needs_build_finished and self._buildCompleteConsumer is not None:
            yield self._buildCompleteConsumer.stopConsuming()
            self._buildCompleteConsumer = None

        if needs_build_finished and self._buildCompleteConsumer is None:
            self._buildCompleteConsumer = yield startConsuming(self.buildComplete,
                                                               ('builds', None, 'finished'))

        if not needs_worker_missing and self._workerMissingConsumer is not None:
            yield self._workerMissingConsumer.stopConsuming()
            self._workerMissingConsumer = None

        if needs_worker_missing and self._workerMissingConsumer is None:
            self._workerMissingConsumer = yield startConsuming(self.workerMissing,
                                                               ('workers', None, 'missing'))

    def create_generators_from_old_args(self, mode, tags, builders, build_set_summary,
                                        message_formatter, subject, add_logs, add_patch, schedulers,
                                        branches, watched_workers,
                                        message_formatter_missing_worker):
        generators = []
        if build_set_summary:
            generators.append(BuildSetStatusGenerator(mode=mode, tags=tags, builders=builders,
                                                      schedulers=schedulers, branches=branches,
                                                      subject=subject, add_logs=add_logs,
                                                      add_patch=add_patch,
                                                      message_formatter=message_formatter))
        else:
            generators.append(BuildStatusGenerator(mode=mode, tags=tags, builders=builders,
                                                   schedulers=schedulers, branches=branches,
                                                   subject=subject, add_logs=add_logs,
                                                   add_patch=add_patch,
                                                   message_formatter=message_formatter))

        if watched_workers is not None and len(watched_workers) > 0:
            generators.append(
                WorkerMissingGenerator(workers=watched_workers,
                                       message_formatter=message_formatter_missing_worker))

        return generators

    def stopService(self):
        yield super().stopService()
        if self._buildsetCompleteConsumer is not None:
            yield self._buildsetCompleteConsumer.stopConsuming()
            self._buildsetCompleteConsumer = None
        if self._buildCompleteConsumer is not None:
            yield self._buildCompleteConsumer.stopConsuming()
            self._buildCompleteConsumer = None
        if self._workerMissingConsumer is not None:
            yield self._workerMissingConsumer.stopConsuming()
            self._workerMissingConsumer = None

    @defer.inlineCallbacks
    def _send_reports_for_type(self, type, key, msg):
        reports = []
        for g in self.generators:
            if isinstance(g, type):
                report = yield g.generate(self.master, self, key, msg)
                if report is not None:
                    reports.append(report)

        if reports:
            yield self.sendMessage(reports)

    @defer.inlineCallbacks
    def buildsetComplete(self, key, msg):
        yield self._send_reports_for_type(BuildSetStatusGenerator, key, msg)

    @defer.inlineCallbacks
    def buildComplete(self, key, msg):
        yield self._send_reports_for_type(BuildStatusGenerator, key, msg)

    @defer.inlineCallbacks
    def workerMissing(self, key, msg):
        yield self._send_reports_for_type(WorkerMissingGenerator, key, msg)

    def getResponsibleUsersForBuild(self, master, buildid):
        # Use library method but subclassers may want to override that
        return utils.getResponsibleUsersForBuild(master, buildid)

    @abc.abstractmethod
    def sendMessage(self, reports):
        pass

    def isWorkerMessageNeeded(self, worker):
        return self.watchedWorkers == 'all' or worker['name'] in self.watchedWorkers
