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

import json
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy.types import Text
from sqlalchemy.types import TypeDecorator

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect


class JsonObject(TypeDecorator):
    """Represents an immutable json-encoded string."""

    cache_ok = True
    impl = Text

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is not None:
            value = json.loads(value)
        else:
            value = {}
        return value
