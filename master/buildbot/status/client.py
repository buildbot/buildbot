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

from buildbot.status.client_compat import PBListener
from buildbot.warnings import warn_deprecated

# This file is here to allow few remaining users of status within Buildbot to use it
# without triggering deprecation warnings

_hush_pyflakes = [
    PBListener
]

warn_deprecated(
    '0.9.0',
    'buildbot.status.client has been deprecated, consume the buildbot.data APIs'
)
