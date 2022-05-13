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


import warnings


class ConfigWarning(Warning):
    """
    Warning for issues in the configuration. Use DeprecatedApiWarning for deprecated APIs
    """


# DeprecationWarning or PendingDeprecationWarning may be used as
# the base class, but by default deprecation warnings are disabled in Python,
# so by default old-API usage warnings will be ignored - this is not what
# we want.
class DeprecatedApiWarning(Warning):
    """
    Warning for deprecated configuration options.
    """


def warn_deprecated(version, msg, stacklevel=2):
    warnings.warn(
        f"[{version} and later] {msg}",
        category=DeprecatedApiWarning,
        stacklevel=stacklevel,
    )
