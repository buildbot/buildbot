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
from twisted.internet import threads

from buildbot import config


class Capture(object):

    """
    Base class for all Capture* classes.
    """

    def __init__(self, routingKey, callback):
        self.routingKey = routingKey
        self._callback = callback
        # parent service and buildmaster to be set when StatsService initialized
        self.parent_svcs = []
        self.master = None

    def _defaultContext(self, msg):
        return {
            "builder_name": self._builder_name,
            "build_number": str(msg['number'])
        }

    def consume(self, routingKey, msg):
        raise NotImplementedError

    @defer.inlineCallbacks
    def _store(self, post_data, series_name, context):
        for svc in self.parent_svcs:
            yield threads.deferToThread(svc.thd_postStatsValue, post_data, series_name,
                                        context)


class CaptureProperty(Capture):

    """
    Convenience wrapper for getting statistics for filtering.
    Filters out build properties specifies in the config file.
    """

    def __init__(self, builder_name, property_name, callback=None):
        self._builder_name = builder_name
        self._property_name = property_name
        routingKey = ("builders", None, "builds", None, "finished")

        def default_callback(props, property_name):
            return props[property_name][0]  # index: 0 - prop_value, 1 - prop_source

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
        if self._builder_name == builder_info['name']:
            properties = yield self.master.data.get(("builds", msg['buildid'], "properties"))
            try:
                ret_val = self._callback(properties, self._property_name)
            except KeyError:
                config.error("CaptureProperty failed."
                             " The property %s not found for build number %s on builder %s."
                             % (self._property_name, msg['number'], self._builder_name))
            context = self._defaultContext(msg)
            series_name = '%s-%s' % (self._builder_name, self._property_name)
            post_data = {
                "name": self._property_name,
                "value": ret_val
            }
            yield self._store(post_data, series_name, context)

        else:
            yield defer.succeed(None)


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
        if self._builder_name == builder_info['name']:
            try:
                ret_val = self._callback(*self._retValParams(msg))
            except Exception as e:
                # catching generic exceptions is okay here since we propagate it
                config.error(self._err_msg(msg) + " Exception raised: " + type(e).__name__ +
                             " with message: " + str(e))
            context = self._defaultContext(msg)
            post_data = {
                self._time_type: ret_val
            }
            series_name = self._builder_name + "-build-times"
            yield self._store(post_data, series_name, context)

        else:
            yield defer.succeed(None)

    def _err_msg(self, build_data):
        msg = "%s failed on build %s on builder %s." % (self.__class__.__name__,
                                                        build_data['number'], self._builder_name)
        return msg


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


class CaptureBuildEndTime(CaptureBuildTimes):

    """
    Capture methods for capturing build start times.
    """

    def __init__(self, builder_name, callback=None):
        def default_callback(end_time):
            return end_time.isoformat()
        if not callback:
            callback = default_callback
        CaptureBuildTimes.__init__(self, builder_name, callback, "end-time")

    def _retValParams(self, msg):
        return [msg['complete_at']]


class CaptureBuildDuration(CaptureBuildTimes):

    """
    Capture methods for capturing build start times.
    """

    def __init__(self, builder_name, report_in='seconds', callback=None):
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


class CaptureData(Capture):

    """
    Capture methods for arbitraty data that may not be stored in the Buildbot database.
    """

    def __init__(self, data_name, builder_name, callback=None):
        self._data_name = data_name
        self._builder_name = builder_name

        def identity(x):
            return x

        if not callback:
            callback = identity

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
        if self._builder_name == builder_info['name'] and self._data_name == msg['data_name']:
            try:
                ret_val = self._callback(msg['post_data'])
            except Exception as e:
                config.error("CaptureData failed for build %s of builder %s."
                             " Exception generated: %s with message %s"
                             % (build_data['number'], self._builder_name, type(e).__name__,
                                str(e)))
            post_data = ret_val
            series_name = '%s-%s' % (self._builder_name, self._data_name)
            context = self._defaultContext(build_data)
            yield self._store(post_data, series_name, context)
