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
from buildbot.data import resultspec
from buildbot.process.results import FAILURE
from buildbot.util.service import BuildbotService
from buildbot.util.ssfilter import SourceStampFilter
from buildbot.util.ssfilter import extract_filter_values


class _FailingSingleBuilderConfig:
    def __init__(self, builders_to_cancel, filter):
        self.builders_to_cancel = builders_to_cancel
        self.filter = filter


class _FailingBuilderConfig:
    def __init__(self):
        self._by_builder = {}

    def add_config(self, builders, builders_to_cancel, filter):
        assert builders is not None

        config = _FailingSingleBuilderConfig(builders_to_cancel, filter)

        for builder in builders:
            self._by_builder.setdefault(builder, []).append(config)

    def get_all_matched(self, builder_name, props):
        assert builder_name is not None

        configs = self._by_builder.get(builder_name, [])
        return [c for c in configs if c.filter.is_matched(props)]


class FailingBuildsetCanceller(BuildbotService):

    compare_attrs = BuildbotService.compare_attrs + ('filters',)

    def checkConfig(self, name, filters):
        FailingBuildsetCanceller.check_filters(filters)

        self.name = name

        self._build_finished_consumer = None

    def reconfigService(self, name, filters):
        self.filters = FailingBuildsetCanceller.filter_tuples_to_filter_set_object(filters)

    @defer.inlineCallbacks
    def startService(self):
        yield super().startService()
        self._build_finished_consumer = \
            yield self.master.mq.startConsuming(self._on_build_finished,
                                                ('builds', None, 'finished'))

    @defer.inlineCallbacks
    def stopService(self):
        yield self._build_finished_consumer.stopConsuming()

    @classmethod
    def check_filters(cls, filters):
        if not isinstance(filters, list):
            config.error(f'{cls.__name__}: The filters argument must be a list of tuples')

        for filter in filters:
            if not isinstance(filter, tuple) or \
                    len(filter) != 3 or \
                    not isinstance(filter[2], SourceStampFilter):
                config.error(('{}: The filters argument must be a list of tuples each of which ' +
                              'contains builders to track as the first item, builders to cancel ' +
                              'as the second and SourceStampFilter as the third'
                              ).format(cls.__name__))

            builders, builders_to_cancel, _ = filter

            try:
                extract_filter_values(builders, 'builders')
                if builders_to_cancel is not None:
                    extract_filter_values(builders_to_cancel, 'builders_to_cancel')
            except Exception as e:
                config.error(f'{cls.__name__}: When processing filter builders: {str(e)}')

    @classmethod
    def filter_tuples_to_filter_set_object(cls, filters):
        filter_set = _FailingBuilderConfig()

        for filter in filters:
            builders, builders_to_cancel, ss_filter = filter

            extract_filter_values(builders, 'builders')

            if builders_to_cancel is not None:
                builders_to_cancel = extract_filter_values(builders_to_cancel, 'builders_to_cancel')

            filter_set.add_config(builders, builders_to_cancel, ss_filter)

        return filter_set

    @defer.inlineCallbacks
    def _on_build_finished(self, key, build):
        if build['results'] != FAILURE:
            return

        buildrequest = yield self.master.data.get(('buildrequests', build['buildrequestid']))
        builder = yield self.master.data.get(("builders", build['builderid']))
        buildset = yield self.master.data.get(('buildsets', buildrequest['buildsetid']))

        sourcestamps = buildset['sourcestamps']

        builders_to_cancel = set()
        for ss in sourcestamps:
            configs = self.filters.get_all_matched(builder['name'], ss)
            for c in configs:
                if builders_to_cancel is not None:
                    if c.builders_to_cancel is None:
                        builders_to_cancel = None
                    else:
                        builders_to_cancel.update(c.builders_to_cancel)

        all_bs_buildrequests = yield self.master.data.get(
            ('buildrequests',),
            filters=[resultspec.Filter('buildsetid', 'eq', [buildset['bsid']]),
                     resultspec.Filter('complete', 'eq', [False])])

        all_bs_buildrequests = [br for br in all_bs_buildrequests
                                if br['buildrequestid'] != buildrequest['buildrequestid']]

        for br in all_bs_buildrequests:
            brid = br['buildrequestid']
            if brid == buildrequest['buildrequestid']:
                continue  # this one has just failed

            br_builder = yield self.master.data.get(("builders", br['builderid']))

            if builders_to_cancel is not None and br_builder['name'] not in builders_to_cancel:
                continue

            reason = 'Build has been cancelled because another build in the same buildset failed'

            self.master.data.control('cancel', {'reason': reason}, ('buildrequests', str(brid)))
