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

from .utils import BuildStatusGeneratorMixin


@implementer(interfaces.IReportGenerator)
class BuildSetStatusGenerator(BuildStatusGeneratorMixin):

    wanted_event_keys = [
        ('buildsets', None, 'complete'),
    ]

    compare_attrs = ['formatter']

    def __init__(self, mode=("failing", "passing", "warnings"),
                 tags=None, builders=None, schedulers=None, branches=None,
                 subject="Buildbot %(result)s in %(title)s on %(builder)s",
                 add_logs=False, add_patch=False, message_formatter=None):
        super().__init__(mode, tags, builders, schedulers, branches, subject, add_logs, add_patch)
        self.formatter = message_formatter
        if self.formatter is None:
            self.formatter = MessageFormatter()

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, message):
        bsid = message['bsid']
        res = yield utils.getDetailsForBuildset(master, bsid,
                                                wantProperties=self.formatter.wantProperties,
                                                wantSteps=self.formatter.wantSteps,
                                                wantPreviousBuild=self._want_previous_build(),
                                                wantLogs=self.formatter.wantLogs)

        builds = res['builds']
        buildset = res['buildset']

        # only include builds for which isMessageNeeded returns true
        builds = [build for build in builds
                  if self.is_message_needed_by_props(build) and
                  self.is_message_needed_by_results(build)]
        if not builds:
            return None

        report = yield self.build_message(self.formatter, master, reporter, "whole buildset",
                                          builds, buildset['results'])
        return report

    def _want_previous_build(self):
        return "change" in self.mode or "problem" in self.mode
