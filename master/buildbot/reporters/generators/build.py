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

from buildbot.reporters import utils

from .utils import BuildStatusGeneratorMixin


class BuildStatusGenerator(BuildStatusGeneratorMixin):

    wanted_event_keys = [
        ('builds', None, 'finished'),
    ]

    def __init__(self, mode=("failing", "passing", "warnings"),
                 tags=None, builders=None, schedulers=None, branches=None,
                 subject="Buildbot %(result)s in %(title)s on %(builder)s",
                 add_logs=False, add_patch=False, message_formatter=None):
        super().__init__(mode, tags, builders, schedulers, branches, subject, add_logs, add_patch,
                         message_formatter)

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, build):
        br = yield master.data.get(("buildrequests", build['buildrequestid']))
        buildset = yield master.data.get(("buildsets", br['buildsetid']))
        yield utils.getDetailsForBuilds(master, buildset, [build],
                                        wantProperties=self.formatter.wantProperties,
                                        wantSteps=self.formatter.wantSteps,
                                        wantPreviousBuild=self._want_previous_build(),
                                        wantLogs=self.formatter.wantLogs)

        # only include builds for which isMessageNeeded returns true
        if not self.is_message_needed(build):
            return None

        report = yield self.build_message(master, reporter, build['builder']['name'], [build],
                                          build['results'])
        return report

    def _want_previous_build(self):
        return "change" in self.mode or "problem" in self.mode

    def _matches_any_tag(self, tags):
        return self.tags and any(tag for tag in self.tags if tag in tags)
