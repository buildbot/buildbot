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

import bisect
import json

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.reporters import utils
from buildbot.reporters.message import MessageFormatterFunction

from .utils import BuildStatusGeneratorMixin


@implementer(interfaces.IReportGenerator)
class BuildCodeIssueCommentsGenerator(BuildStatusGeneratorMixin):

    wanted_event_keys = [
        ('builds', None, 'finished'),
    ]

    compare_attrs = ['formatter']

    def __init__(self, diffinfo_data_name=None, tags=None, builders=None, schedulers=None,
                 branches=None, message_formatter=None):
        super().__init__('all', tags, builders, schedulers, branches, subject='', add_logs=False,
                         add_patch=False)
        self.diffinfo_data_name = diffinfo_data_name
        self.formatter = message_formatter
        if self.formatter is None:
            self.formatter = MessageFormatterFunction(lambda ctx: ctx['message'], 'plain')

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, build):
        _, _, event = key
        if event != 'finished':
            return None

        yield utils.getDetailsForBuild(master, build,
                                       wantProperties=self.formatter.wantProperties,
                                       wantSteps=self.formatter.wantSteps,
                                       wantPreviousBuild=False,
                                       wantLogs=self.formatter.wantLogs)

        if not self.is_message_needed_by_props(build):
            return None
        if not self.is_message_needed_by_results(build):
            return None

        report = yield self._build_report(self.formatter, master, reporter, build)
        return report

    def _get_target_changes_by_path(self, diff_info):
        hunks_by_path = {}
        for file_info in diff_info:
            hunks = [(hunk['ts'], hunk['tl']) for hunk in file_info['hunks']]
            if not hunks:
                continue
            hunks.sort()

            hunks_by_path[file_info['target_file']] = hunks
        return hunks_by_path

    def _is_result_usable(self, result):
        return result.get('test_code_path') is not None and result.get('line') is not None

    def _is_result_in_target_diff(self, target_changes_by_path, result):
        changes_in_path = target_changes_by_path.get(result['test_code_path'])
        if not changes_in_path:
            return False

        result_line = result['line']

        preceding_change_i = bisect.bisect(changes_in_path, (result_line + 1, -1))
        if preceding_change_i == 0:
            return False  # there's no change with start position earlier than the test result line
        preceding_change_start, preceding_change_length = changes_in_path[preceding_change_i - 1]

        return result_line >= preceding_change_start and \
            result_line < preceding_change_start + preceding_change_length

    @defer.inlineCallbacks
    def _get_usable_results_in_changed_lines(self, master, target_changes_by_path, result_sets):
        results_in_changed_lines = []

        for result_set in result_sets:
            if result_set['category'] != 'code_issue':
                continue
            if result_set['value_unit'] != 'message':
                continue

            results = yield master.data.get(('test_result_sets', result_set['test_result_setid'],
                                             'results'))

            results = [tr for tr in results
                       if self._is_result_usable(tr) and
                       self._is_result_in_target_diff(target_changes_by_path, tr)]

            results_in_changed_lines.extend(results)
        return results_in_changed_lines

    @defer.inlineCallbacks
    def _build_report(self, formatter, master, reporter, build):
        users = yield reporter.getResponsibleUsersForBuild(master, build['buildid'])

        build_data = yield master.data.get(('builds', build['buildid'], 'data',
                                            self.diffinfo_data_name, 'value'))

        target_changes_by_path = self._get_target_changes_by_path(json.loads(build_data['raw']))

        result_sets = yield master.data.get(('builds', build['buildid'], 'test_result_sets'))

        results_in_changed_lines = \
            yield self._get_usable_results_in_changed_lines(master, target_changes_by_path,
                                                            result_sets)

        result_body = []
        for result in results_in_changed_lines:

            buildmsg = yield formatter.format_message_for_build(master, build, mode=self.mode,
                                                                users=users,
                                                                message=result['value'])

            result_body.append({
                'codebase': '',
                'path': result['test_code_path'],
                'line': result['line'],
                'body': buildmsg['body']
            })

        return {
            'body': result_body,
            'subject': None,
            'type': 'code_comments',
            'results': build['results'],
            'builds': [build],
            'users': list(users),
            'patches': None,
            'logs': None
        }
