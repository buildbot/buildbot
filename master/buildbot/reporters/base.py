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
from twisted.python import log
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

from buildbot import config
from buildbot.reporters import utils
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.generators.buildset import BuildSetStatusGenerator
from buildbot.reporters.generators.worker import WorkerMissingGenerator
from buildbot.util import service
from buildbot.util import tuplematch
from buildbot.warnings import warn_deprecated

ENCODING = 'utf-8'


class ReporterBase(service.BuildbotService):
    name = None
    __meta__ = abc.ABCMeta

    compare_attrs = ['generators']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generators = None
        self._event_consumers = []

    def checkConfig(self, mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    addLogs=False, addPatch=False,
                    schedulers=None, branches=None,
                    watchedWorkers=None, messageFormatterMissingWorker=None,
                    generators=None,
                    _has_old_arg_names=None):

        old_arg_names = {
            'mode': mode != ("failing", "passing", "warnings"),
            'tags': tags is not None,
            'builders': builders is not None,
            'buildSetSummary': buildSetSummary is not False,
            'messageFormatter': messageFormatter is not None,
            'subject': subject != "Buildbot %(result)s in %(title)s on %(builder)s",
            'addLogs': addLogs is not False,
            'addPatch': addPatch is not False,
            'schedulers': schedulers is not None,
            'branches': branches is not None,
            'watchedWorkers': watchedWorkers is not None,
            'messageFormatterMissingWorker': messageFormatterMissingWorker is not None,
        }
        if _has_old_arg_names is not None:
            old_arg_names.update(_has_old_arg_names)

        passed_old_arg_names = [k for k, v in old_arg_names.items() if v]

        if passed_old_arg_names:

            old_arg_names_msg = ', '.join(passed_old_arg_names)
            if generators is not None:
                config.error(("can't specify generators and deprecated notifier arguments ({}) "
                              "at the same time").format(old_arg_names_msg))
            warn_deprecated('2.9.0',
                            ('The arguments {} passed to {} have been deprecated. Use generators '
                             'instead').format(old_arg_names_msg, self.__class__.__name__))

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

        for consumer in self._event_consumers:
            yield consumer.stopConsuming()
        self._event_consumers = []

        if generators is None:
            generators = self.create_generators_from_old_args(mode, tags, builders, buildSetSummary,
                                                              messageFormatter, subject, addLogs,
                                                              addPatch, schedulers,
                                                              branches, watchedWorkers,
                                                              messageFormatterMissingWorker)

        self.generators = generators

        wanted_event_keys = set()
        for g in self.generators:
            wanted_event_keys.update(g.wanted_event_keys)

        for key in sorted(list(wanted_event_keys)):
            consumer = yield self.master.mq.startConsuming(self._got_event, key)
            self._event_consumers.append(consumer)

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

    @defer.inlineCallbacks
    def stopService(self):
        for consumer in self._event_consumers:
            yield consumer.stopConsuming()
        self._event_consumers = []
        yield super().stopService()

    def _does_generator_want_key(self, generator, key):
        for filter in generator.wanted_event_keys:
            if tuplematch.matchTuple(key, filter):
                return True
        return False

    @defer.inlineCallbacks
    def _got_event(self, key, msg):
        try:
            reports = []
            for g in self.generators:
                if self._does_generator_want_key(g, key):
                    report = yield g.generate(self.master, self, key, msg)
                    if report is not None:
                        reports.append(report)

            if reports:
                yield self.sendMessage(reports)
        except Exception as e:
            log.err(e, 'Got exception when handling reporter events')

    def getResponsibleUsersForBuild(self, master, buildid):
        # Use library method but subclassers may want to override that
        return utils.getResponsibleUsersForBuild(master, buildid)

    @abc.abstractmethod
    def sendMessage(self, reports):
        pass


NotifierBase = ReporterBase
deprecatedModuleAttribute(
    Version("buildbot", 2, 9, 0),
    message="Use ReporterBase instead.",
    moduleName="buildbot.reporters.base",
    name="NotifierBase",
)
