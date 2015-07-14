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


class Capture(object):
    """
    Base class for all Capture* classes.
    """
    def __init__(self, routingKey, callback):
        self.routingKey = routingKey
        self.callback = callback
        # parent service and buildmaster to be set when StatsService initialized
        self.parent_svcs = []
        self.master = None

    def defaultContext(self, msg):
        return {
            "builder_name": self.builder_name,
            "build_number": str(msg['number'])
        }

    def consumer(self, routingKey, msg):
        raise NotImplementedError


class CaptureProperty(Capture):
    """
    Convenience wrapper for getting statistics for filtering.
    Filters out build properties specifies in the config file.
    """
    def __init__(self, builder_name, property_name, callback=None):
        self.builder_name = builder_name
        self.property_name = property_name
        routingKey = ("builders", None, "builds", None, "finished")

        def default_callback(props, property_name):
            return props[property_name][0]  # index: 0 - prop_value, 1 - prop_source

        if not callback:
            callback = default_callback

        Capture.__init__(self, routingKey, callback)

    @defer.inlineCallbacks
    def consumer(self, routingKey, msg):
        """
        Consumer for this (CaptureProperty) class. Gets the properties from data api and
        send them to the storage backends.
        """
        builder_info = yield self.master.data.get(("builders", msg['builderid']))
        if self.builder_name == builder_info['name']:
            properties = yield self.master.data.get(("builds", msg['buildid'], "properties"))
            ret_val = self.callback(properties, self.property_name)
            context = self.defaultContext(msg)
            series_name = self.builder_name + "-" + self.property_name
            post_data = {
                "name": self.property_name,
                "value": ret_val
            }
            for svc in self.parent_svcs:
                yield threads.deferToThread(svc.postStatsValue, post_data, series_name,
                                            context)

        else:
            yield defer.succeed(None)


class CaptureBuildTimes(Capture):
    """
    Capture methods for capturing build start times.
    """
    def __init__(self, builder_name, callback):
        self.builder_name = builder_name
        routingKey = ("builders", None, "builds", None, "finished")
        Capture.__init__(self, routingKey, callback)

    @defer.inlineCallbacks
    def consumer(self, routingKey, msg):
        """
        Consumer for CaptureBuildStartTime. Gets the build start time.
        """
        builder_info = yield self.master.data.get(("builders", msg['builderid']))
        if self.builder_name == builder_info['name']:
            ret_val = self.callback(*self.retValParams(msg))
            context = self.defaultContext(msg)
            post_data = {
                self._time_type: ret_val
            }
            series_name = self.builder_name + "-build-times"
            for svc in self.parent_svcs:
                yield threads.deferToThread(svc.postStatsValue, post_data, series_name,
                                            context)

        else:
            yield defer.returnValue(None)


class CaptureBuildStartTime(CaptureBuildTimes):
    """
    Capture methods for capturing build start times.
    """
    def __init__(self, builder_name, callback=None):
        def default_callback(start_time):
            return start_time.isoformat()
        if not callback:
            callback = default_callback
        self._time_type = "start-time"
        CaptureBuildTimes.__init__(self, builder_name, callback)

    def retValParams(self, msg):
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
        self._time_type = "end-time"
        CaptureBuildTimes.__init__(self, builder_name, callback)

    def retValParams(self, msg):
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
        self._time_type = "duration"
        CaptureBuildTimes.__init__(self, builder_name, callback)

    def retValParams(self, msg):
        return [msg['started_at'], msg['complete_at']]


class CaptureData(Capture):
    """
    Capture methods for arbitraty data that may not be stored in the Buildbot database.
    """
    def __init__(self, data_name, builder_name, callback=None):
        self.data_name = data_name
        self.builder_name = builder_name

        if not callback:
            callback = lambda x: x

        routingKey = ("stats-yieldMetricsValue", "stats-yield-data")
        Capture.__init__(self, routingKey, callback)

    @defer.inlineCallbacks
    def consumer(self, routingKey, msg):
        build_data = msg['build_data']
        builder_info = yield self.master.data.get(("builders", build_data['builderid']))
        if self.builder_name == builder_info['name'] and self.data_name == msg['data_name']:
            ret_val = self.callback(msg['post_data'])
            context = self.defaultContext(build_data)
            post_data = ret_val
            series_name = self.builder_name + "-" + self.data_name
            for svc in self.parent_svcs:
                yield threads.deferToThread(svc.postStatsValue, post_data, series_name,
                                            context)

        else:
            yield defer.returnValue(None)
