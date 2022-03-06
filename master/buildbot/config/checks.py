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
