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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
import re

from twisted.internet import defer
from twisted.internet import threads

from buildbot import config
from buildbot.errors import CaptureCallbackError


class Capture(object):

    """
    Base class for all Capture* classes.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, routingKey, callback):
        self.routingKey = routingKey
        self._callback = callback
        # parent service and buildmaster to be set when StatsService
        # initialized
        self.parent_svcs = []
        self.master = None

    def _defaultContext(self, msg, builder_name):
        return {
            "builder_name": builder_name,
            "build_number": str(msg['number'])
        }

    @abc.abstractmethod
    def consume(self, routingKey, msg):
        pass

    @defer.inlineCallbacks
    def _store(self, post_data, series_name, context):
        for svc in self.parent_svcs:
            yield threads.deferToThread(svc.thd_postStatsValue, post_data, series_name,
                                        context)


class CapturePropertyBase(Capture):

    """
    A base class for CaptureProperty* classes.
    """

    def __init__(self, property_name, callback=None, regex=False):
        self._property_name = property_name
        self._regex = regex
        routingKey = ("builders", None, "builds", None, "finished")

        def default_callback(props, property_name):
            # index: 0 - prop_value, 1 - prop_source
            return props[property_name][0]

        if not callback:
            callback = default_callback

        Capture.__init__(self, routingKey, callback)

    @defer.inlineCallbacks
    def consume(self, routingKey, msg):
        """
        Consumer for this (CaptureProperty) class. Gets the properties from data api and
        send them to the storage backends.
        """
        builder_info = yield self.master.data.get(("builders", msg['builderid']))

        if self._builder_name_matches(builder_info):
            properties = yield self.master.data.get(("builds", msg['buildid'], "properties"))

            if self._regex:
                filtered_prop_names = [
                    pn for pn in properties if re.match(self._property_name, pn)]
            else:
                filtered_prop_names = [self._property_name]

            for pn in filtered_prop_names:
                try:
                    ret_val = self._callback(properties, pn)
                except KeyError:
                    raise CaptureCallbackError("CaptureProperty failed."
                                               " The property %s not found for build number %s on"
                                               " builder %s."
                                               % (pn, msg['number'], builder_info['name']))
                context = self._defaultContext(msg, builder_info['name'])
                series_name = "%s-%s" % (builder_info['name'], pn)
                post_data = {
                    "name": pn,
                    "value": ret_val
                }
                yield self._store(post_data, series_name, context)

        else:
            yield defer.succeed(None)

    @abc.abstractmethod
    def _builder_name_matches(self, builder_info):
        pass


class CaptureProperty(CapturePropertyBase):

    """
    Convenience wrapper for getting statistics for filtering.
    Filters out build properties specifies in the config file.
    """

    def __init__(self, builder_name, property_name, callback=None, regex=False):
        self._builder_name = builder_name

        CapturePropertyBase.__init__(self, property_name, callback, regex)

    def _builder_name_matches(self, builder_info):
        return self._builder_name == builder_info['name']


class CapturePropertyAllBuilders(CapturePropertyBase):

    """
    Capture class for filtering out build properties for all builds.
    """

    def _builder_name_matches(self, builder_info):
        # Since we need to match all builders, we simply return True here.
        return True


class CaptureBuildTimes(Capture):

    """
    Capture methods for capturing build start times.
    """

    def __init__(self, builder_name, callback, time_type):
        self._builder_name = builder_name
        routingKey = ("builders", None, "builds", None, "finished")
        self._time_type = time_type
        Capture.__init__(self, routingKey, callback)

    @defer.inlineCallbacks
    def consume(self, routingKey, msg):
        """
        Consumer for CaptureBuildStartTime. Gets the build start time.
        """
        builder_info = yield self.master.data.get(("builders", msg['builderid']))
        if self._builder_name_matches(builder_info):
            try:
                ret_val = self._callback(*self._retValParams(msg))
            except Exception as e:
                # catching generic exceptions is okay here since we propagate
                # it
                raise CaptureCallbackError("%s Exception raised: %s with message: %s" %
                                           (self._err_msg(msg, builder_info['name']),
                                            type(e).__name__, str(e)))

            context = self._defaultContext(msg, builder_info['name'])
            post_data = {
                self._time_type: ret_val
            }
            series_name = "%s-build-times" % builder_info['name']
            yield self._store(post_data, series_name, context)

        else:
            yield defer.succeed(None)

    def _err_msg(self, build_data, builder_name):
        msg = "%s failed on build %s on builder %s." % (self.__class__.__name__,
                                                        build_data['number'], builder_name)
        return msg

    @abc.abstractmethod
    def _retValParams(self, msg):
        pass

    @abc.abstractmethod
    def _builder_name_matches(self, builder_info):
        pass


class CaptureBuildStartTime(CaptureBuildTimes):

    """
    Capture methods for capturing build start times.
    """

    def __init__(self, builder_name, callback=None):
        def default_callback(start_time):
            return start_time.isoformat()
        if not callback:
            callback = default_callback
        CaptureBuildTimes.__init__(self, builder_name, callback, "start-time")

    def _retValParams(self, msg):
        return [msg['started_at']]

    def _builder_name_matches(self, builder_info):
        return self._builder_name == builder_info['name']


class CaptureBuildStartTimeAllBuilders(CaptureBuildStartTime):

    """
    Capture methods for capturing build start times for all builders.
    """

    def __init__(self, callback=None):
        CaptureBuildStartTime.__init__(self, None, callback)

    def _builder_name_matches(self, builder_info):
        # Match all builders so simply return True
        return True


class CaptureBuildEndTime(CaptureBuildTimes):

    """
    Capture methods for capturing build end times.
    """

    def __init__(self, builder_name, callback=None):
        def default_callback(end_time):
            return end_time.isoformat()
        if not callback:
            callback = default_callback
        CaptureBuildTimes.__init__(self, builder_name, callback, "end-time")

    def _retValParams(self, msg):
        return [msg['complete_at']]

    def _builder_name_matches(self, builder_info):
        return self._builder_name == builder_info['name']


class CaptureBuildEndTimeAllBuilders(CaptureBuildEndTime):

    """
    Capture methods for capturing build end times on all builders.
    """

    def __init__(self, callback=None):
        CaptureBuildEndTime.__init__(self, None, callback)

    def _builder_name_matches(self, builder_info):
        # Match all builders so simply return True
        return True


class CaptureBuildDuration(CaptureBuildTimes):

    """
    Capture methods for capturing build start times.
    """

    def __init__(self, builder_name, report_in='seconds', callback=None):
        if report_in not in ['seconds', 'minutes', 'hours']:
            config.error("Error during initialization of class %s."
                         " `report_in` parameter must be one of 'seconds', 'minutes' or 'hours'"
                         % (self.__class__.__name__))

        def default_callback(start_time, end_time):
            divisor = 1
            # it's a closure
            if report_in == 'minutes':
                divisor = 60
            elif report_in == 'hours':
                divisor = 60 * 60
            duration = end_time - start_time
            # cannot use duration.total_seconds() on Python 2.6
            duration = ((duration.microseconds + (duration.seconds +
                                                  duration.days * 24 * 3600) * 1e6) / 1e6)
            return duration / divisor

        if not callback:
            callback = default_callback
        CaptureBuildTimes.__init__(self, builder_name, callback, "duration")

    def _retValParams(self, msg):
        return [msg['started_at'], msg['complete_at']]

    def _builder_name_matches(self, builder_info):
        return self._builder_name == builder_info['name']


class CaptureBuildDurationAllBuilders(CaptureBuildDuration):

    """
    Capture methods for capturing build durations on all builders.
    """

    def __init__(self, report_in='seconds', callback=None):
        CaptureBuildDuration.__init__(self, None, report_in, callback)

    def _builder_name_matches(self, builder_info):
        # Match all builders so simply return True
        return True


class CaptureDataBase(Capture):

    """
    Base class for CaptureData methods.
    """

    def __init__(self, data_name, callback=None):
        self._data_name = data_name

        def identity(x):
            return x

        if not callback:
            callback = identity

        # this is the routing key which is used to register consumers on to mq layer
        # this following key created in StatsService.yieldMetricsValue and used
        # here
        routingKey = ("stats-yieldMetricsValue", "stats-yield-data")
        Capture.__init__(self, routingKey, callback)

    @defer.inlineCallbacks
    def consume(self, routingKey, msg):
        """
        Consumer for this (CaptureData) class. Gets the data sent from yieldMetricsValue and
        sends it to the storage backends.
        """
        build_data = msg['build_data']
        builder_info = yield self.master.data.get(("builders", build_data['builderid']))

        if self._builder_name_matches(builder_info) and self._data_name == msg['data_name']:
            try:
                ret_val = self._callback(msg['post_data'])
            except Exception as e:
                raise CaptureCallbackError("CaptureData failed for build %s of builder %s."
                                           " Exception generated: %s with message %s"
                                           % (build_data['number'], builder_info['name'],
                                              type(e).__name__, str(e)))
            post_data = ret_val
            series_name = '%s-%s' % (builder_info['name'], self._data_name)
            context = self._defaultContext(build_data, builder_info['name'])
            yield self._store(post_data, series_name, context)

    @abc.abstractmethod
    def _builder_name_matches(self, builder_info):
        pass


class CaptureData(CaptureDataBase):

    """
    Capture methods for arbitrary data that may not be stored in the Buildbot database.
    """

    def __init__(self, data_name, builder_name, callback=None):
        self._builder_name = builder_name

        CaptureDataBase.__init__(self, data_name, callback)

    def _builder_name_matches(self, builder_info):
        return self._builder_name == builder_info['name']


class CaptureDataAllBuilders(CaptureDataBase):

    """
    Capture methods for arbitrary data that may not be stored in the Buildbot database.
    """

    def _builder_name_matches(self, builder_info):
        return True
