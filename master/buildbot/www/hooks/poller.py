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

# This change hook allows GitHub or a hand crafted curl invocation to "knock on
# the door" and trigger a change source to poll.

from __future__ import absolute_import
from __future__ import print_function

from buildbot.changes.base import PollingChangeSource


def getChanges(req, options=None):
    change_svc = req.site.master.change_svc
    poll_all = "poller" not in req.args

    allow_all = True
    allowed = []
    if isinstance(options, dict) and "allowed" in options:
        allow_all = False
        allowed = options["allowed"]

    pollers = []

    for source in change_svc:
        if not isinstance(source, PollingChangeSource):
            continue
        if not hasattr(source, "name"):
            continue
        if not poll_all and source.name not in req.args['poller']:
            continue
        if not allow_all and source.name not in allowed:
            continue
        pollers.append(source)

    if not poll_all:
        missing = set(req.args['poller']) - set(s.name for s in pollers)
        if missing:
            raise ValueError("Could not find pollers: %s" % ",".join(missing))

    for p in pollers:
        p.force()

    return [], None
