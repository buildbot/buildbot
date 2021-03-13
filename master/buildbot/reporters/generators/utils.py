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
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import statusToString


class BuildStatusGeneratorMixin(util.ComparableMixin):

    possible_modes = ("change", "failing", "passing", "problem", "warnings", "exception",
                      "cancelled")

    compare_attrs = ['mode', 'tags', 'builders', 'schedulers', 'branches', 'subject', 'add_logs',
                     'add_patch']

    def __init__(self, mode, tags, builders, schedulers, branches, subject, add_logs, add_patch):
        self.mode = self._compute_shortcut_modes(mode)

        self.tags = tags
        self.builders = builders
        self.schedulers = schedulers
        self.branches = branches
        self.subject = subject
        self.add_logs = add_logs
        self.add_patch = add_patch

    def check(self):
        self._verify_build_generator_mode(self.mode)

        if self.subject is not None and '\n' in self.subject:
            config.error('Newlines are not allowed in message subjects')

        list_or_none_params = [
            ('tags', self.tags),
            ('builders', self.builders),
            ('schedulers', self.schedulers),
            ('branches', self.branches),
        ]
        for name, param in list_or_none_params:
            self._verify_list_or_none_param(name, param)

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

    def is_message_needed_by_props(self, build):
        # here is where we actually do something.
        builder = build['builder']
        scheduler = build['properties'].get('scheduler', [None])[0]
        branch = build['properties'].get('branch', [None])[0]

        if self.builders is not None and builder['name'] not in self.builders:
            return False
        if self.schedulers is not None and scheduler not in self.schedulers:
            return False
        if self.branches is not None and branch not in self.branches:
            return False
        if self.tags is not None and not self._matches_any_tag(builder['tags']):
            return False
        return True

    def is_message_needed_by_results(self, build):
        results = build['results']
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

    def _merge_msgtype(self, msgtype, new_msgtype):
        if new_msgtype is None:
            return msgtype, False
        if msgtype is None:
            return new_msgtype, True
        if msgtype != new_msgtype:
            log.msg(('{}: Incompatible message types for multiple builds ({} and {}). Ignoring'
                     ).format(self, msgtype, new_msgtype))
            return msgtype, False

        return msgtype, True

    def _merge_subject(self, subject, new_subject):
        if subject is None and new_subject is not None:
            return new_subject
        return subject

    def _merge_body(self, body, new_body):
        if body is None:
            return new_body, True
        if new_body is None:
            return body, True

        if isinstance(body, str) and isinstance(new_body, str):
            return body + new_body, True

        if isinstance(body, list) and isinstance(new_body, list):
            return body + new_body, True

        log.msg(('{}: Incompatible message body types for multiple builds ({} and {}). Ignoring'
                 ).format(self, type(body), type(new_body)))
        return body, False

    @defer.inlineCallbacks
    def build_message(self, formatter, master, reporter, name, builds, results):
        # The given builds must refer to builds from a single buildset
        patches = []
        logs = []
        body = None
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

            blamelist = yield reporter.getResponsibleUsersForBuild(master, build['buildid'])
            users.update(set(blamelist))

            buildmsg = yield formatter.format_message_for_build(self.mode, name, build,
                                                                master, blamelist)

            msgtype, ok = self._merge_msgtype(msgtype, buildmsg['type'])
            if not ok:
                continue

            subject = self._merge_subject(subject, buildmsg['subject'])

            body, ok = self._merge_body(body, buildmsg['body'])
            if not ok:
                continue

        if subject is None and self.subject is not None:
            subject = self.subject % {'result': statusToString(results),
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

    def _verify_list_or_none_param(self, name, param):
        if param is not None and not isinstance(param, list):
            config.error("{} must be a list or None".format(name))

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

    def _matches_any_tag(self, tags):
        return self.tags and any(tag for tag in self.tags if tag in tags)
