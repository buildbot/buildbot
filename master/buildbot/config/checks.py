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

from typing import Any
from typing import TypeVar

from buildbot.config.errors import error

T = TypeVar('T')


def check_param_length(value: Any, name: str, max_length: int) -> None:
    if isinstance(value, str) and len(value) > max_length:
        error(f"{name} '{value}' exceeds maximum length of {max_length}")

    qualified_name = f"{type(value).__module__}.{type(value).__name__}"
    if qualified_name == 'buildbot.process.properties.Interpolate':
        interpolations: tuple[str, ...] | dict[str, Any]
        if value.args:
            interpolations = tuple([''] * len(value.args))
        else:
            interpolations = {k: '' for k in value.interpolations}
        shortest_value = value.fmtstring % interpolations
        if len(shortest_value) > max_length:
            error(
                f"{name} '{value}' (shortest interpolation) exceeds maximum length of {max_length}"
            )


def check_param_type(
    value: Any,
    default_value: T,
    class_inst: Any,
    name: str,
    types: tuple[type, ...],
    types_msg: str,
) -> T:
    if isinstance(value, types):
        return value  # type: ignore[return-value]
    error(f"{class_inst.__name__} argument {name} must be an instance of {types_msg}")
    return default_value


def check_param_bool(value: Any, class_inst: Any, name: str) -> bool:
    return check_param_type(value, False, class_inst, name, (bool,), "bool")


def check_param_str(value: Any, class_inst: Any, name: str) -> str:
    return check_param_type(value, "(unknown)", class_inst, name, (str,), "str")


def check_param_str_none(value: Any, class_inst: Any, name: str) -> str | None:
    return check_param_type(value, "(unknown)", class_inst, name, (str, type(None)), "str or None")


def check_param_int(value: Any, class_inst: Any, name: str) -> int:
    return check_param_type(value, 0, class_inst, name, (int,), "int")


def check_param_int_none(value: Any, class_inst: Any, name: str) -> int | None:
    return check_param_type(value, None, class_inst, name, (int, type(None)), "int or None")


def check_param_number_none(value: Any, class_inst: Any, name: str) -> int | float | None:
    return check_param_type(
        value, 0, class_inst, name, (int, float, type(None)), "int or float or None"
    )


def check_markdown_support(class_inst: Any) -> bool:
    try:
        import markdown  # pylint: disable=import-outside-toplevel

        _ = markdown
        return True
    except ImportError:  # pragma: no cover
        error(
            f"{class_inst.__name__}: Markdown library is required in order to use "
            "markdown format ('pip install Markdown')"
        )
        return False
