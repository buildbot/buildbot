
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

from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

from buildbot.buildslave.libvirt import Connection
from buildbot.buildslave.libvirt import Domain
from buildbot.buildslave.libvirt import LibVirtSlave

for _attr in ["LibVirtSlave", "Connection", "Domain"]:
    deprecatedModuleAttribute(Version("Buildbot", 0, 8, 8),
                              "It has been moved to buildbot.buildslave.libvirt",
                              "buildbot.libvirtbuildslave", _attr)

_hush_pyflakes = [
    LibVirtSlave,
    Domain,
    Connection,
]
