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

from __future__ import absolute_import
from __future__ import print_function

import re
from collections import namedtuple

# The regex is matching more than it should and is not intended to be an url validator.
# It is intended to efficiently and reliably extract information from the various examples
# that are described in the unit tests.

_giturlmatcher = re.compile(
    r'(?P<proto>(https?://|ssh://|git://|))'
    r'((?P<user>.*)@)?'
    r'(?P<domain>[^\/:]+)(:((?P<port>[0-9]+)/)?|/)'
    r'(?P<owner>.+)/(?P<repo>[^/]+?)(\.git)?$')

GitUrl = namedtuple('GitUrl', ['proto', 'user', 'domain', 'port', 'owner', 'repo'])


def giturlparse(url):
    res = _giturlmatcher.match(url)
    if res is not None:
        port = res.group("port")
        if port is not None:
            port = int(port)
        proto = res.group("proto")
        if proto:
            proto = proto[:-3]
        else:
            proto = 'ssh'  # implicit proto is ssh
        return GitUrl(
            proto, res.group('user'),
            res.group("domain"), port, res.group("owner"),
            res.group("repo"))
