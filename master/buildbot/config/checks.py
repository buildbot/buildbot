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

from buildbot.config.errors import error


def check_param_length(value, name, max_length):
    if isinstance(value, str) and len(value) > max_length:
        error(f"{name} '{value}' exceeds maximum length of {max_length}")

    qualified_name = f"{type(value).__module__}.{type(value).__name__}"
    if qualified_name == 'buildbot.process.properties.Interpolate':
        if value.args:
            interpolations = tuple([''] * len(value.args))
        else:
            interpolations = {k: '' for k in value.interpolations}
        shortest_value = value.fmtstring % interpolations
        if len(shortest_value) > max_length:
            error(f"{name} '{value}' (shortest interpolation) exceeds maximum length of "
                  f"{max_length}")


def check_param_type(value, default_value, class_inst, name, types, types_msg):
    if isinstance(value, types):
        return value
    error(f"{class_inst.__name__} argument {name} must be an instance of {types_msg}")
    return default_value


def check_param_str(value, class_inst, name):
    return check_param_type(value, "(unknown)", class_inst, name, (str,), "str")


def check_param_str_none(value, class_inst, name):
    return check_param_type(value, "(unknown)", class_inst, name, (str, type(None)), "str or None")


def check_param_int(value, class_inst, name):
    return check_param_type(value, 0, class_inst, name, (int,), "int")


def check_param_int_none(value, class_inst, name):
    return check_param_type(value, None, class_inst, name, (int, type(None)), "int or None")


def check_markdown_support(class_inst):
    try:
        import markdown  # pylint: disable=import-outside-toplevel
        [markdown]
        return True
    except ImportError:  # pragma: no cover
        error(f"{class_inst.__name__}: Markdown library is required in order to use "
              "markdown format ('pip install Markdown')")
        return False
