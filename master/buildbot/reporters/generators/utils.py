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

from buildbot import config
from buildbot import util
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.reporters.message import MessageFormatter as DefaultMessageFormatter


class BuildStatusGeneratorMixin(util.ComparableMixin):

    possible_modes = ("change", "failing", "passing", "problem", "warnings", "exception",
                      "cancelled")

    compare_attrs = ['mode', 'tags', 'builders', 'schedulers', 'branches', 'subject', 'add_logs',
                     'add_patch', 'formatter']

    def __init__(self, mode, tags, builders, schedulers, branches, subject, add_logs, add_patch,
                 message_formatter):
        self.mode = self._compute_shortcut_modes(mode)

        self.tags = tags
        self.builders = builders
        self.schedulers = schedulers
        self.branches = branches
        self.subject = subject
        self.add_logs = add_logs
        self.add_patch = add_patch
        self.formatter = message_formatter
        if self.formatter is None:
            self.formatter = DefaultMessageFormatter()

    def check(self):
        self._verify_build_generator_mode(self.mode)

        if '\n' in self.subject:
            config.error('Newlines are not allowed in message subjects')

        # you should either limit on builders or tags, not both
        if self.builders is not None and self.tags is not None:
            config.error("Please specify only builders or tags to include - not both.")

    def generate_name(self):
        name = self.__class__.__name__
        if self.tags is not None:
            name += "_tags_" + "+".join(self.tags)
        if self.builders is not None:
            name += "_builders_" + "+".join(self.builders)
        if self.schedulers is not None:
            name += "_schedulers_" + "+".join(self.schedulers)
        if self.branches is not None:
            name += "_branches_" + "+".join(self.branches)
        name += "_".join(self.mode)
        return name

    def _should_attach_log(self, log):
        if isinstance(self.add_logs, bool):
            return self.add_logs

        if log['name'] in self.add_logs:
            return True

        long_name = "{}.{}".format(log['stepname'], log['name'])
        if long_name in self.add_logs:
            return True

        return False

    def is_message_needed(self, build):
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
        if self.tags is not None and not self._matches_any_tag(builder['tags']):
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
    def build_message(self, master, reporter, name, builds, results):
        patches = []
        logs = []
        body = ""
        subject = None
        msgtype = None
        users = set()
        for build in builds:
            if self.add_patch:
                ss_list = build['buildset']['sourcestamps']

                for ss in ss_list:
                    if 'patch' in ss and ss['patch'] is not None:
                        patches.append(ss['patch'])

            if self.add_logs:
                build_logs = yield self._get_logs_for_build(master, build)
                if isinstance(self.add_logs, list):
                    build_logs = [log for log in build_logs if self._should_attach_log(log)]
                logs.extend(build_logs)

            if 'prev_build' in build and build['prev_build'] is not None:
                previous_results = build['prev_build']['results']
            else:
                previous_results = None
            blamelist = yield reporter.getResponsibleUsersForBuild(master, build['buildid'])
            buildmsg = yield self.formatter.formatMessageForBuildResults(
                self.mode, name, build['buildset'], build, master, previous_results, blamelist)
            users.update(set(blamelist))
            msgtype = buildmsg['type']
            body += buildmsg['body']
            if 'subject' in buildmsg:
                subject = buildmsg['subject']

        if subject is None:
            subject = self.subject % {'result': Results[results],
                                      'projectName': master.config.title,
                                      'title': master.config.title,
                                      'builder': name}

        return {
            'body': body,
            'subject': subject,
            'type': msgtype,
            'builder_name': name,
            'results': results,
            'builds': builds,
            'users': list(users),
            'patches': patches,
            'logs': logs
        }

    @defer.inlineCallbacks
    def _get_logs_for_build(self, master, build):
        all_logs = []
        steps = yield master.data.get(('builds', build['buildid'], "steps"))
        for step in steps:
            logs = yield master.data.get(("steps", step['stepid'], 'logs'))
            for l in logs:
                l['stepname'] = step['name']
                l['content'] = yield master.data.get(("logs", l['logid'], 'contents'))
                all_logs.append(l)
        return all_logs

    def _verify_build_generator_mode(self, mode):
        for m in self._compute_shortcut_modes(mode):
            if m not in self.possible_modes:
                if m == "all":
                    config.error("mode 'all' is not valid in an iterator and must be "
                                 "passed in as a separate string")
                else:
                    config.error("mode {} is not a valid mode".format(m))

    def _compute_shortcut_modes(self, mode):
        if isinstance(mode, str):
            if mode == "all":
                mode = ("failing", "passing", "warnings",
                        "exception", "cancelled")
            elif mode == "warnings":
                mode = ("failing", "warnings")
            else:
                mode = (mode,)
        return mode
