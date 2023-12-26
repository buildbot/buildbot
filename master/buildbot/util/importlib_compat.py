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

# This module is for backward compatibility of importlib.


def entry_points_get(entry_points, group):
    """ Since Python 3.12 dictionary access is removed and replaced by new interface.
        see: https://github.com/python/cpython/issues/97781
    """
    if hasattr(entry_points, "select"):
        return entry_points.select(group=group)
    else:
        if isinstance(entry_points, list):
            filtered_entry_points = []
            for ep in entry_points:
                if ep.group == group:
                    filtered_entry_points.append(ep)
            return filtered_entry_points
        else:
            return entry_points.get(group, [])
