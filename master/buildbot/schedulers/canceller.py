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
from typing import ClassVar
from typing import Sequence

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


class _TrackedBuildRequest:
    def __init__(self, brid, builder_name, start_time, ss_tuples):
        self.start_time = start_time
        self.builder_name = builder_name
        self.brid = brid
        self.ss_tuples = ss_tuples

    def __str__(self):
        return (
            f'_TrackedBuildRequest({self.brid}, {self.builder_name} '
            f'{self.start_time}, {self.ss_tuples})'
        )

    __repr__ = __str__


class _OldBuildrequestTracker:
    def __init__(self, reactor, filter, branch_key, on_cancel):
        self.reactor = reactor
        self.filter = filter
        self.branch_key = branch_key
        self.on_cancel = on_cancel

        # We need to track build requests by IDs so that when such build request finishes we know
        # what we no longer need to track. We also need to track build requests by source code
        # branch, so that we can cancel build requests when branch sees new commits. Branch is
        # identified by a tuple of project, codebase, repository and branch.
        #
        # Note that a single branch may run multiple builds. Also, changes are not a source for
        # build request cancelling because a change may not result in builds being started due to
        # user scheduler configuration. In such case it makes sense to let the build finish.

        # (is_build, id) -> _TrackedBuildRequest
        self.br_by_id = {}
        self.br_by_ss = {}
        self.change_time_by_ss = {}
        self._change_count_since_clean = 0

    def reconfig(self, filter, branch_key):
        self.filter = filter
        self.branch_key = branch_key

    def is_buildrequest_tracked(self, br_id):
        return br_id in self.br_by_id

    def on_new_buildrequest(self, brid, builder_name, sourcestamps):
        self._maybe_cancel_new_obsoleted_buildrequest(builder_name, sourcestamps)
        self._add_new_buildrequest(brid, builder_name, sourcestamps)

    def _add_new_buildrequest(self, brid, builder_name, sourcestamps):
        now = self.reactor.seconds()

        matched_ss = []

        for ss in sourcestamps:
            if ss['branch'] is None:
                return

            # Note that it's enough to match build by a single branch from a single codebase
            if self.filter.is_matched(builder_name, ss):
                matched_ss.append(ss)

        if not matched_ss:
            return

        ss_tuples = [
            (ss['project'], ss['codebase'], ss['repository'], self.branch_key(ss))
            for ss in matched_ss
        ]

        tracked_br = _TrackedBuildRequest(brid, builder_name, now, ss_tuples)
        self.br_by_id[brid] = tracked_br

        for ss_tuple in ss_tuples:
            br_dict = self.br_by_ss.setdefault(ss_tuple, {})
            br_dict[tracked_br.brid] = tracked_br

    def _maybe_cancel_new_obsoleted_buildrequest(self, builder_name, sourcestamps):
        for sourcestamp in sourcestamps:
            ss_tuple = (
                sourcestamp['project'],
                sourcestamp['codebase'],
                sourcestamp['repository'],
                self.branch_key(sourcestamp),
            )

            newest_change_time = self.change_time_by_ss.get(ss_tuple, None)
            if newest_change_time is None:
                # Don't cancel any buildrequests if the cancelling buildrequest does not come from
                # a change.
                continue

            br_dict = self.br_by_ss.get(ss_tuple, None)
            if br_dict is None:
                continue

            brids_to_cancel = []
            for tracked_br in list(br_dict.values()):
                if tracked_br.builder_name != builder_name:
                    continue

                if newest_change_time <= tracked_br.start_time:
                    # The existing build request is newer than the change, thus change should not
                    # be a reason to cancel it.
                    continue

                del self.br_by_id[tracked_br.brid]

                # Clear the canceled buildrequest from self.br_by_ss
                for i_ss_tuple in tracked_br.ss_tuples:
                    other_br_dict = self.br_by_ss.get(i_ss_tuple, None)
                    if other_br_dict is None:
                        raise KeyError(
                            f'{self.__class__.__name__}: Could not find running builds '
                            f'by tuple {i_ss_tuple}'
                        )

                    del other_br_dict[tracked_br.brid]
                    if not other_br_dict:
                        del self.br_by_ss[i_ss_tuple]

                brids_to_cancel.append(tracked_br.brid)

            for brid in brids_to_cancel:
                self.on_cancel(brid)

    def on_complete_buildrequest(self, brid):
        tracked_br = self.br_by_id.pop(brid, None)
        if tracked_br is None:
            return

        for ss_tuple in tracked_br.ss_tuples:
            br_dict = self.br_by_ss.get(ss_tuple, None)
            if br_dict is None:
                raise KeyError(
                    f'{self.__class__.__name__}: Could not find finished builds by tuple {ss_tuple}'
                )

            del br_dict[tracked_br.brid]
            if not br_dict:
                del self.br_by_ss[ss_tuple]

    def on_change(self, change):
        now = self.reactor.seconds()

        ss_tuple = (
            change['project'],
            change['codebase'],
            change['repository'],
            self.branch_key(change),
        )

        # Note that now is monotonically increasing
        self.change_time_by_ss[ss_tuple] = now

        self._change_count_since_clean += 1
        if self._change_count_since_clean >= 1000:
            self.change_time_by_ss = {
                ss_tuple: ss_now
                for ss_tuple, ss_now in self.change_time_by_ss.items()
                if now - ss_now < 60 * 10
            }
            self._change_count_since_clean = 0


class OldBuildCanceller(BuildbotService):
    compare_attrs: ClassVar[Sequence[str]] = (*BuildbotService.compare_attrs, 'filters')

    def checkConfig(self, name, filters, branch_key=None):
        OldBuildCanceller.check_filters(filters)

        self.name = name

        self._buildrequest_new_consumer = None
        self._buildrequest_complete_consumer = None

        self._build_tracker = None
        self._reconfiguring = False
        self._completed_buildrequests_while_reconfiguring = []

    @defer.inlineCallbacks
    def reconfigService(self, name, filters, branch_key=None):
        # While reconfiguring we acquire a list of currently pending build
        # requests and seed the build tracker with these. We need to ensure that even if some
        # builds or build requests finish during this process, the tracker gets to know about
        # the changes in correct order. In order to do that, we defer all build request completion
        # notifications to after the reconfig finishes.
        #
        # Note that old builds are cancelled according to the configuration that was live when they
        # were created, so for already tracked builds we don't need to do anything.
        self._reconfiguring = True

        if branch_key is None:
            branch_key = self._default_branch_key

        filter_set_object = OldBuildCanceller.filter_tuples_to_filter_set_object(filters)

        if self._build_tracker is None:
            self._build_tracker = _OldBuildrequestTracker(
                self.master.reactor, filter_set_object, branch_key, self._cancel_buildrequest
            )
        else:
            self._build_tracker.reconfig(filter_set_object, branch_key)

        all_running_buildrequests = yield self.master.data.get(
            ('buildrequests',), filters=[resultspec.Filter('complete', 'eq', [False])]
        )

        for breq in all_running_buildrequests:
            if self._build_tracker.is_buildrequest_tracked(breq['buildrequestid']):
                continue
            yield self._on_buildrequest_new(None, breq)

        self._reconfiguring = False

        completed_breqs = self._completed_buildrequests_while_reconfiguring
        self._completed_buildrequests_while_reconfiguring = []

        for breq in completed_breqs:
            self._build_tracker.on_complete_buildrequest(breq['buildrequestid'])

    @defer.inlineCallbacks
    def startService(self):
        yield super().startService()
        self._change_consumer = yield self.master.mq.startConsuming(
            self._on_change, ('changes', None, 'new')
        )
        self._buildrequest_new_consumer = yield self.master.mq.startConsuming(
            self._on_buildrequest_new, ('buildrequests', None, 'new')
        )
        self._buildrequest_complete_consumer = yield self.master.mq.startConsuming(
            self._on_buildrequest_complete, ('buildrequests', None, 'complete')
        )

    @defer.inlineCallbacks
    def stopService(self):
        yield self._change_consumer.stopConsuming()
        yield self._buildrequest_new_consumer.stopConsuming()
        yield self._buildrequest_complete_consumer.stopConsuming()

    @classmethod
    def check_filters(cls, filters):
        if not isinstance(filters, list):
            config.error(f'{cls.__name__}: The filters argument must be a list of tuples')

        for filter in filters:
            if (
                not isinstance(filter, tuple)
                or len(filter) != 2
                or not isinstance(filter[1], SourceStampFilter)
            ):
                config.error(
                    (
                        '{}: The filters argument must be a list of tuples each of which '
                        + 'contains builders as the first item and SourceStampFilter as '
                        + 'the second'
                    ).format(cls.__name__)
                )

            builders, _ = filter

            try:
                extract_filter_values(builders, 'builders')
            except Exception as e:
                config.error(f'{cls.__name__}: When processing filter builders: {e!s}')

    @classmethod
    def filter_tuples_to_filter_set_object(cls, filters):
        filter_set = _OldBuildFilterSet()

        for filter in filters:
            builders, ss_filter = filter
            filter_set.add_filter(extract_filter_values(builders, 'builders'), ss_filter)

        return filter_set

    def _default_branch_key(self, ss_or_change):
        branch = ss_or_change['branch']
        if branch is None:
            return None

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
    def _on_buildrequest_new(self, key, breq):
        builder = yield self.master.data.get(("builders", breq['builderid']))
        buildset = yield self.master.data.get(('buildsets', breq['buildsetid']))

        self._build_tracker.on_new_buildrequest(
            breq['buildrequestid'], builder['name'], buildset['sourcestamps']
        )

    def _on_buildrequest_complete(self, key, breq):
        if self._reconfiguring:
            self._completed_buildrequests_while_reconfiguring.append(breq)
            return
        self._build_tracker.on_complete_buildrequest(breq['buildrequestid'])

    def _cancel_buildrequest(self, brid):
        self.master.data.control(
            'cancel',
            {'reason': 'Build request has been obsoleted by a newer commit'},
            ('buildrequests', str(brid)),
        )
