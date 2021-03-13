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

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.reporters import utils
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.message import MessageFormatterRenderable

from .utils import BuildStatusGeneratorMixin


@implementer(interfaces.IReportGenerator)
class BuildStatusGenerator(BuildStatusGeneratorMixin):

    wanted_event_keys = [
        ('builds', None, 'finished'),
    ]

    compare_attrs = ['formatter']

    def __init__(self, mode=("failing", "passing", "warnings"),
                 tags=None, builders=None, schedulers=None, branches=None,
                 subject="Buildbot %(result)s in %(title)s on %(builder)s",
                 add_logs=False, add_patch=False, report_new=False, message_formatter=None):
        super().__init__(mode, tags, builders, schedulers, branches, subject, add_logs, add_patch)
        self.formatter = message_formatter
        if self.formatter is None:
            self.formatter = MessageFormatter()

        if report_new:
            self.wanted_event_keys = [
                ('builds', None, 'finished'),
                ('builds', None, 'new'),
            ]

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, build):
        _, _, event = key
        is_new = event == 'new'
        want_previous_build = False if is_new else self._want_previous_build()

        yield utils.getDetailsForBuild(master, build,
                                       wantProperties=self.formatter.wantProperties,
                                       wantSteps=self.formatter.wantSteps,
                                       wantPreviousBuild=want_previous_build,
                                       wantLogs=self.formatter.wantLogs)

        if not self.is_message_needed_by_props(build):
            return None
        if not is_new and not self.is_message_needed_by_results(build):
            return None

        report = yield self.build_message(self.formatter, master, reporter,
                                          build['builder']['name'], [build],
                                          build['results'])
        return report

    def _want_previous_build(self):
        return "change" in self.mode or "problem" in self.mode


@implementer(interfaces.IReportGenerator)
class BuildStartEndStatusGenerator(BuildStatusGeneratorMixin):

    wanted_event_keys = [
        ('builds', None, 'new'),
        ('builds', None, 'finished'),
    ]

    compare_attrs = ['start_formatter', 'end_formatter']

    def __init__(self, tags=None, builders=None, schedulers=None, branches=None, add_logs=False,
                 add_patch=False, start_formatter=None, end_formatter=None):

        super().__init__('all', tags, builders, schedulers, branches, None, add_logs, add_patch)
        self.start_formatter = start_formatter
        if self.start_formatter is None:
            self.start_formatter = MessageFormatterRenderable('Build started.')
        self.end_formatter = end_formatter
        if self.end_formatter is None:
            self.end_formatter = MessageFormatterRenderable('Build done.')

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, build):
        _, _, event = key
        is_new = event == 'new'

        formatter = self.start_formatter if is_new else self.end_formatter

        yield utils.getDetailsForBuild(master, build,
                                       wantProperties=formatter.wantProperties,
                                       wantSteps=formatter.wantSteps,
                                       wantLogs=formatter.wantLogs)

        if not self.is_message_needed_by_props(build):
            return None

        report = yield self.build_message(formatter, master, reporter, build['builder']['name'],
                                          [build], build['results'])
        return report
