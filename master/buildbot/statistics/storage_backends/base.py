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
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from buildbot.statistics.capture import Capture


class StatsStorageBase:
    """
    Base class for sub service responsible for passing on stats data to
    a storage backend
    """

    __metaclass__ = abc.ABCMeta

    captures: list[Capture]

    @abc.abstractmethod
    def thd_postStatsValue(
        self,
        post_data: dict[str, Any],
        series_name: str,
        context: dict[str, str] | None = None,
    ) -> None:
        pass
