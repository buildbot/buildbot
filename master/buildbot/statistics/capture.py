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

from __future__ import annotations

import abc
import datetime
import re
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.internet import threads

from buildbot import config
from buildbot.errors import CaptureCallbackError

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


class Capture:
    """
    Base class for all Capture* classes.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        routingKey: tuple[str | None, ...],
        callback: Callable[..., Any],
    ) -> None:
        self.routingKey = routingKey
        self._callback = callback
        # parent service and buildmaster to be set when StatsService
        # initialized
        self.parent_svcs: list[Any] = []
        self.master: Any = None

    def _defaultContext(self, msg: dict[str, Any], builder_name: str) -> dict[str, str]:
        return {"builder_name": builder_name, "build_number": str(msg['number'])}

    @abc.abstractmethod
    def consume(self, routingKey: tuple[str | None, ...], msg: dict[str, Any]) -> Any:
        pass

    @defer.inlineCallbacks
    def _store(
        self,
        post_data: dict[str, Any],
        series_name: str,
        context: dict[str, str],
    ) -> InlineCallbacksType[None]:
        for svc in self.parent_svcs:
            yield threads.deferToThread(svc.thd_postStatsValue, post_data, series_name, context)


class CapturePropertyBase(Capture):
    """
    A base class for CaptureProperty* classes.
    """

    def __init__(
        self,
        property_name: str,
        callback: Callable[..., Any] | None = None,
        regex: bool = False,
    ) -> None:
        self._property_name = property_name
        self._regex = regex
        routingKey: tuple[str | None, ...] = ("builders", None, "builds", None, "finished")

        def default_callback(props: dict[str, Any], property_name: str) -> Any:
            # index: 0 - prop_value, 1 - prop_source
            return props[property_name][0]

        if not callback:
            callback = default_callback

        super().__init__(routingKey, callback)

    @defer.inlineCallbacks
    def consume(
        self, routingKey: tuple[str | None, ...], msg: dict[str, Any]
    ) -> InlineCallbacksType[None]:
        """
        Consumer for this (CaptureProperty) class. Gets the properties from data api and
        send them to the storage backends.
        """
        builder_info = yield self.master.data.get(("builders", msg['builderid']))

        if self._builder_name_matches(builder_info):
            properties = yield self.master.data.get(("builds", msg['buildid'], "properties"))

            if self._regex:
                filtered_prop_names = [pn for pn in properties if re.match(self._property_name, pn)]
            else:
                filtered_prop_names = [self._property_name]

            for pn in filtered_prop_names:
                try:
                    ret_val = self._callback(properties, pn)
                except KeyError as e:
                    raise CaptureCallbackError(
                        "CaptureProperty failed."
                        f" The property {pn} not found for build number "
                        f"{msg['number']} on"
                        f" builder {builder_info['name']}."
                    ) from e
                context = self._defaultContext(msg, builder_info['name'])
                series_name = f"{builder_info['name']}-{pn}"
                post_data = {"name": pn, "value": ret_val}
                yield self._store(post_data, series_name, context)

        else:
            yield defer.succeed(None)

    @abc.abstractmethod
    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        pass


class CaptureProperty(CapturePropertyBase):
    """
    Convenience wrapper for getting statistics for filtering.
    Filters out build properties specifies in the config file.
    """

    def __init__(
        self,
        builder_name: str,
        property_name: str,
        callback: Callable[..., Any] | None = None,
        regex: bool = False,
    ) -> None:
        self._builder_name = builder_name

        super().__init__(property_name, callback, regex)

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        return self._builder_name == builder_info['name']


class CapturePropertyAllBuilders(CapturePropertyBase):
    """
    Capture class for filtering out build properties for all builds.
    """

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        # Since we need to match all builders, we simply return True here.
        return True


class CaptureBuildTimes(Capture):
    """
    Capture methods for capturing build start times.
    """

    def __init__(
        self,
        builder_name: str | None,
        callback: Callable[..., Any],
        time_type: str,
    ) -> None:
        self._builder_name = builder_name
        routingKey: tuple[str | None, ...] = ("builders", None, "builds", None, "finished")
        self._time_type = time_type
        super().__init__(routingKey, callback)

    @defer.inlineCallbacks
    def consume(
        self, routingKey: tuple[str | None, ...], msg: dict[str, Any]
    ) -> InlineCallbacksType[None]:
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
                raise CaptureCallbackError(
                    f"{self._err_msg(msg, builder_info['name'])} "
                    f"Exception raised: {type(e).__name__} "
                    f"with message: {e!s}"
                ) from e

            context = self._defaultContext(msg, builder_info['name'])
            post_data = {self._time_type: ret_val}
            series_name = f"{builder_info['name']}-build-times"
            yield self._store(post_data, series_name, context)

        else:
            yield defer.succeed(None)

    def _err_msg(self, build_data: dict[str, Any], builder_name: str) -> str:
        msg = (
            f"{self.__class__.__name__} failed on build {build_data['number']} "
            f"on builder {builder_name}."
        )
        return msg

    @abc.abstractmethod
    def _retValParams(self, msg: dict[str, Any]) -> list[Any]:
        pass

    @abc.abstractmethod
    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        pass


class CaptureBuildStartTime(CaptureBuildTimes):
    """
    Capture methods for capturing build start times.
    """

    def __init__(
        self, builder_name: str | None, callback: Callable[..., Any] | None = None
    ) -> None:
        def default_callback(start_time: datetime.datetime) -> str:
            return start_time.isoformat()

        if not callback:
            callback = default_callback
        super().__init__(builder_name, callback, "start-time")

    def _retValParams(self, msg: dict[str, Any]) -> list[Any]:
        return [msg['started_at']]

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        return self._builder_name == builder_info['name']


class CaptureBuildStartTimeAllBuilders(CaptureBuildStartTime):
    """
    Capture methods for capturing build start times for all builders.
    """

    def __init__(self, callback: Callable[..., Any] | None = None) -> None:
        super().__init__(None, callback)

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        # Match all builders so simply return True
        return True


class CaptureBuildEndTime(CaptureBuildTimes):
    """
    Capture methods for capturing build end times.
    """

    def __init__(
        self, builder_name: str | None, callback: Callable[..., Any] | None = None
    ) -> None:
        def default_callback(end_time: datetime.datetime) -> str:
            return end_time.isoformat()

        if not callback:
            callback = default_callback
        super().__init__(builder_name, callback, "end-time")

    def _retValParams(self, msg: dict[str, Any]) -> list[Any]:
        return [msg['complete_at']]

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        return self._builder_name == builder_info['name']


class CaptureBuildEndTimeAllBuilders(CaptureBuildEndTime):
    """
    Capture methods for capturing build end times on all builders.
    """

    def __init__(self, callback: Callable[..., Any] | None = None) -> None:
        super().__init__(None, callback)

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        # Match all builders so simply return True
        return True


class CaptureBuildDuration(CaptureBuildTimes):
    """
    Capture methods for capturing build start times.
    """

    def __init__(
        self,
        builder_name: str | None,
        report_in: str = 'seconds',
        callback: Callable[..., Any] | None = None,
    ) -> None:
        if report_in not in ['seconds', 'minutes', 'hours']:
            config.error(
                f"Error during initialization of class {self.__class__.__name__}."
                " `report_in` parameter must be one of 'seconds', 'minutes' or 'hours'"
            )

        def default_callback(start_time: datetime.datetime, end_time: datetime.datetime) -> float:
            divisor = 1
            # it's a closure
            if report_in == 'minutes':
                divisor = 60
            elif report_in == 'hours':
                divisor = 60 * 60
            if end_time < start_time:
                duration = datetime.timedelta(0)
            else:
                duration = end_time - start_time
            return duration.total_seconds() / divisor

        if not callback:
            callback = default_callback
        super().__init__(builder_name, callback, "duration")

    def _retValParams(self, msg: dict[str, Any]) -> list[Any]:
        return [msg['started_at'], msg['complete_at']]

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        return self._builder_name == builder_info['name']


class CaptureBuildDurationAllBuilders(CaptureBuildDuration):
    """
    Capture methods for capturing build durations on all builders.
    """

    def __init__(
        self, report_in: str = 'seconds', callback: Callable[..., Any] | None = None
    ) -> None:
        super().__init__(None, report_in, callback)

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        # Match all builders so simply return True
        return True


class CaptureDataBase(Capture):
    """
    Base class for CaptureData methods.
    """

    def __init__(self, data_name: str, callback: Callable[..., Any] | None = None) -> None:
        self._data_name = data_name

        def identity(x: Any) -> Any:
            return x

        if not callback:
            callback = identity

        # this is the routing key which is used to register consumers on to mq layer
        # this following key created in StatsService.yieldMetricsValue and used
        # here
        routingKey: tuple[str | None, ...] = ("stats-yieldMetricsValue", "stats-yield-data")
        super().__init__(routingKey, callback)

    @defer.inlineCallbacks
    def consume(
        self, routingKey: tuple[str | None, ...], msg: dict[str, Any]
    ) -> InlineCallbacksType[None]:
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
                raise CaptureCallbackError(
                    f"CaptureData failed for build {build_data['number']} "
                    f"of builder {builder_info['name']}. "
                    f"Exception generated: {type(e).__name__} "
                    f"with message {e!s}"
                ) from e
            post_data = ret_val
            series_name = f"{builder_info['name']}-{self._data_name}"
            context = self._defaultContext(build_data, builder_info['name'])
            yield self._store(post_data, series_name, context)

    @abc.abstractmethod
    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        pass


class CaptureData(CaptureDataBase):
    """
    Capture methods for arbitrary data that may not be stored in the Buildbot database.
    """

    def __init__(
        self, data_name: str, builder_name: str, callback: Callable[..., Any] | None = None
    ) -> None:
        self._builder_name = builder_name

        super().__init__(data_name, callback)

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        return self._builder_name == builder_info['name']


class CaptureDataAllBuilders(CaptureDataBase):
    """
    Capture methods for arbitrary data that may not be stored in the Buildbot database.
    """

    def _builder_name_matches(self, builder_info: dict[str, Any]) -> bool:
        return True
