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

import re

from twisted.internet import defer

from buildbot import config
from buildbot.data import resultspec
from buildbot.util.service import BuildbotService
from buildbot.util.ssfilter import SourceStampFilter
from buildbot.util.ssfilter import extract_filter_values


class _OldBuildFilterSet:
    def __init__(self):
        self._by_builder = {}

    def add_filter(self, builders, filter):
        assert builders is not None

        for builder in builders:
            self._by_builder.setdefault(builder, []).append(filter)

    def is_matched(self, builder_name, props):
        assert builder_name is not None

        filters = self._by_builder.get(builder_name, [])
        for filter in filters:
            if filter.is_matched(props):
                return True
        return False


class _TrackedCancellable:
    def __init__(self, id_tuple, ss_tuples):
        self.id_tuple = id_tuple
        self.ss_tuples = ss_tuples


class _OldBuildTracker:

    def __init__(self, filter, branch_key, on_cancel_cancellable):
        self.filter = filter
        self.branch_key = branch_key
        self.on_cancel_cancellable = on_cancel_cancellable

        # We need to track builds by build IDs so that when such build finishes we know what we
        # no longer need to track. We also need to track builds by source code branch, so that
        # we can cancel builds when branch sees new commits. Branch is identified by a tuple
        # of project, codebase, repository and branch.
        #
        # Note that a single branch may run multiple builds.

        # (is_build, id) -> _TrackedCancellable
        self.tracked_by_id_tuple = {}
        self.tracked_by_ss = {}

    def reconfig(self, filter, branch_key):
        self.filter = filter
        self.branch_key = branch_key

    def is_build_tracked(self, build_id):
        return (True, build_id) in self.tracked_by_id_tuple

    def is_buildrequest_tracked(self, br_id):
        return (False, br_id) in self.tracked_by_id_tuple

    def on_new_build(self, build_id, builder_name, sourcestamps):
        self._on_new_cancellable((True, build_id), builder_name, sourcestamps)

    def on_new_buildrequest(self, breq_id, builder_name, sourcestamps):
        self._on_new_cancellable((False, breq_id), builder_name, sourcestamps)

    def _on_new_cancellable(self, id_tuple, builder_name, sourcestamps):
        matched_ss = []

        for ss in sourcestamps:
            if ss['branch'] is None:
                return

            # Note that it's enough to match build by a single branch from a single codebase
            if self.filter.is_matched(builder_name, ss):
                matched_ss.append(ss)

        if not matched_ss:
            return

        ss_tuples = [(ss['project'], ss['codebase'], ss['repository'], self.branch_key(ss))
                     for ss in matched_ss]

        tracked_canc = _TrackedCancellable(id_tuple, ss_tuples)
        self.tracked_by_id_tuple[id_tuple] = tracked_canc

        for ss_tuple in ss_tuples:
            canc_dict = self.tracked_by_ss.setdefault(ss_tuple, {})
            canc_dict[tracked_canc.id_tuple] = tracked_canc

    def on_finished_build(self, build_id):
        self._on_complete_cancellable((True, build_id))

    def on_complete_buildrequest(self, br_id):
        self._on_complete_cancellable((False, br_id))

    def _on_complete_cancellable(self, id_tuple):
        tracked_canc = self.tracked_by_id_tuple.pop(id_tuple, None)
        if tracked_canc is None:
            return

        for ss_tuple in tracked_canc.ss_tuples:
            canc_dict = self.tracked_by_ss.get(ss_tuple, None)
            if canc_dict is None:
                raise KeyError(f'{self.__class__.__name__}: Could not find finished builds '
                               f'by tuple {ss_tuple}')

            del canc_dict[tracked_canc.id_tuple]
            if not canc_dict:
                del self.tracked_by_ss[ss_tuple]

    def on_change(self, change):
        ss_tuple = (change['project'], change['codebase'], change['repository'],
                    self.branch_key(change))

        canc_dict = self.tracked_by_ss.pop(ss_tuple, None)
        if canc_dict is None:
            return

        for tracked_canc in canc_dict.values():
            del self.tracked_by_id_tuple[tracked_canc.id_tuple]

            if len(tracked_canc.ss_tuples) == 1:
                # majority of configurations will only contain single-codebase builds and for these
                # tracked_by_ss has been cleared above already.
                continue

            for i_ss_tuple in tracked_canc.ss_tuples:
                if i_ss_tuple == ss_tuple:
                    continue  # the current sourcestamp, which has already been cleared

                other_canc_dict = self.tracked_by_ss.get(i_ss_tuple, None)
                if other_canc_dict is None:
                    raise KeyError(f'{self.__class__.__name__}: Could not find running builds '
                                   f'by tuple {i_ss_tuple}')

                del other_canc_dict[tracked_canc.id_tuple]
                if not other_canc_dict:
                    del self.tracked_by_ss[i_ss_tuple]

        for id_tuple in canc_dict.keys():
            self.on_cancel_cancellable(id_tuple)


class OldBuildCanceller(BuildbotService):

    compare_attrs = BuildbotService.compare_attrs + ('filters',)

    def checkConfig(self, name, filters, branch_key=None):
        OldBuildCanceller.check_filters(filters)

        self.name = name

        self._change_consumer = None
        self._build_new_consumer = None
        self._build_finished_consumer = None
        self._buildrequest_new_consumer = None
        self._buildrequest_complete_consumer = None

        self._build_tracker = None
        self._reconfiguring = False
        self._finished_builds_while_reconfiguring = []
        self._completed_buildrequests_while_reconfiguring = []

    @defer.inlineCallbacks
    def reconfigService(self, name, filters, branch_key=None):
        # While reconfiguring we acquire a list of currently running builds or pending build
        # requests and seed the build tracker with these. We need to ensure that even if some
        # builds or build requests finish during this process, the tracker gets to know about
        # the changes in correct order. In order to do that, we defer all build finish
        # notifications to after the reconfig finishes.
        #
        # Note that old builds are cancelled according to the configuration that was live when they
        # were created, so for already tracked builds we don't need to do anything.
        self._reconfiguring = True

        if branch_key is None:
            branch_key = self._default_branch_key

        filter_set_object = OldBuildCanceller.filter_tuples_to_filter_set_object(filters)

        if self._build_tracker is None:
            self._build_tracker = _OldBuildTracker(filter_set_object, branch_key,
                                                   self._cancel_cancellable)
        else:
            self._build_tracker.reconfig(filter_set_object, branch_key)

        all_running_buildrequests = yield self.master.data.get(
            ('buildrequests',), filters=[resultspec.Filter('complete', 'eq', [False])])

        for breq in all_running_buildrequests:
            if self._build_tracker.is_buildrequest_tracked(breq['buildrequestid']):
                continue
            yield self._on_buildrequest_new(None, breq)

        all_running_builds = yield self.master.data.get(
            ('builds',), filters=[resultspec.Filter('complete', 'eq', [False])])

        for build in all_running_builds:
            if self._build_tracker.is_build_tracked(build['buildid']):
                continue
            yield self._on_build_new(None, build)

        self._reconfiguring = False

        finished_builds = self._finished_builds_while_reconfiguring
        self._finished_builds_while_reconfiguring = []

        completed_breqs = self._completed_buildrequests_while_reconfiguring
        self._completed_buildrequests_while_reconfiguring = []

        for build in finished_builds:
            self._build_tracker.on_finished_build(build['buildid'])
        for breq in completed_breqs:
            self._build_tracker.on_complete_buildrequest(breq['buildrequestid'])

    @defer.inlineCallbacks
    def startService(self):
        yield super().startService()
        self._change_consumer = \
            yield self.master.mq.startConsuming(self._on_change, ('changes', None, 'new'))
        self._build_new_consumer = \
            yield self.master.mq.startConsuming(self._on_build_new, ('builds', None, 'new'))
        self._build_finished_consumer = \
            yield self.master.mq.startConsuming(self._on_build_finished,
                                                ('builds', None, 'finished'))
        self._buildrequest_new_consumer = \
            yield self.master.mq.startConsuming(self._on_buildrequest_new,
                                                ('buildrequests', None, 'new'))
        self._buildrequest_complete_consumer = \
            yield self.master.mq.startConsuming(self._on_buildrequest_complete,
                                                ('buildrequests', None, 'complete'))

    @defer.inlineCallbacks
    def stopService(self):
        yield self._change_consumer.stopConsuming()
        yield self._build_new_consumer.stopConsuming()
        yield self._build_finished_consumer.stopConsuming()
        yield self._buildrequest_new_consumer.stopConsuming()
        yield self._buildrequest_complete_consumer.stopConsuming()

    @classmethod
    def check_filters(cls, filters):
        if not isinstance(filters, list):
            config.error(f'{cls.__name__}: The filters argument must be a list of tuples')

        for filter in filters:
            if not isinstance(filter, tuple) or \
                    len(filter) != 2 or \
                    not isinstance(filter[1], SourceStampFilter):
                config.error(('{}: The filters argument must be a list of tuples each of which ' +
                              'contains builders as the first item and SourceStampFilter as ' +
                              'the second').format(cls.__name__))

            builders, _ = filter

            try:
                extract_filter_values(builders, 'builders')
            except Exception as e:
                config.error(f'{cls.__name__}: When processing filter builders: {str(e)}')

    @classmethod
    def filter_tuples_to_filter_set_object(cls, filters):
        filter_set = _OldBuildFilterSet()

        for filter in filters:
            builders, ss_filter = filter
            filter_set.add_filter(extract_filter_values(builders, 'builders'), ss_filter)

        return filter_set

    def _default_branch_key(self, ss_or_change):
        branch = ss_or_change['branch']

        # On some VCS systems each iteration of a PR gets its own branch. We want to track all
        # iterations of the PR as a single unit.
        if branch.startswith('refs/changes/'):
            m = re.match(r'refs/changes/(\d+)/(\d+)/\d+', branch)
            if m is not None:
                return f'refs/changes/{m.group(1)}/{m.group(2)}'

        return branch

    def _on_change(self, key, change):
        self._build_tracker.on_change(change)

    @defer.inlineCallbacks
    def _on_build_new(self, key, build):
        buildrequest = yield self.master.data.get(('buildrequests', build['buildrequestid']))
        builder = yield self.master.data.get(("builders", build['builderid']))
        buildset = yield self.master.data.get(('buildsets', buildrequest['buildsetid']))

        self._build_tracker.on_new_build(build['buildid'], builder['name'],
                                         buildset['sourcestamps'])

    @defer.inlineCallbacks
    def _on_buildrequest_new(self, key, breq):
        builder = yield self.master.data.get(("builders", breq['builderid']))
        buildset = yield self.master.data.get(('buildsets', breq['buildsetid']))

        self._build_tracker.on_new_buildrequest(breq['buildrequestid'], builder['name'],
                                                buildset['sourcestamps'])

    def _on_build_finished(self, key, build):
        if self._reconfiguring:
            self._finished_builds_while_reconfiguring.append(build)
            return

        self._build_tracker.on_finished_build(build['buildid'])

    def _on_buildrequest_complete(self, key, breq):
        if self._reconfiguring:
            self._completed_buildrequests_while_reconfiguring.append(breq)
            return
        self._build_tracker.on_complete_buildrequest(breq['buildrequestid'])

    def _cancel_cancellable(self, id_tuple):
        is_build, id = id_tuple
        if is_build:
            self.master.data.control('stop',
                                     {'reason': 'Build has been obsoleted by a newer commit'},
                                     ('builds', str(id)))
        else:
            self.master.data.control('cancel',
                                     {'reason':
                                         'Build request has been obsoleted by a newer commit'},
                                     ('buildrequests', str(id)))
