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

from .utils import BuildStatusGeneratorMixin


@implementer(interfaces.IReportGenerator)
class BuildStatusGenerator(BuildStatusGeneratorMixin):

    wanted_event_keys = [
        ('builds', None, 'finished'),
    ]

    def __init__(self, mode=("failing", "passing", "warnings"),
                 tags=None, builders=None, schedulers=None, branches=None,
                 subject="Buildbot %(result)s in %(title)s on %(builder)s",
                 add_logs=False, add_patch=False, report_new=False, message_formatter=None,
                 _want_previous_build=None):
        super().__init__(mode, tags, builders, schedulers, branches, subject, add_logs, add_patch,
                         message_formatter)
        self._report_new = report_new

        # TODO: private and deprecated, included only to support HttpStatusPushBase
        self._want_previous_build_override = _want_previous_build

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
        if self._want_previous_build_override is not None:
            want_previous_build = self._want_previous_build_override

        yield utils.getDetailsForBuild(master, build,
                                       wantProperties=self.formatter.wantProperties,
                                       wantSteps=self.formatter.wantSteps,
                                       wantPreviousBuild=want_previous_build,
                                       wantLogs=self.formatter.wantLogs)

        if not self.is_message_needed_by_props(build):
            return None
        if not is_new and not self.is_message_needed_by_results(build):
            return None

        report = yield self.build_message(master, reporter, build['builder']['name'], [build],
                                          build['results'])
        return report

    def _want_previous_build(self):
        return "change" in self.mode or "problem" in self.mode

    def _matches_any_tag(self, tags):
        return self.tags and any(tag for tag in self.tags if tag in tags)
