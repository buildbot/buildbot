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

# This change hook allows GitHub or a hand crafted curl inovcation to "knock on
# the door" and trigger a change source to poll.

from buildbot.changes.base import PollingChangeSource


def getChanges(req, options=None):
    change_svc = req.site.buildbot_service.master.change_svc

    if not "poller" in req.args:
        raise ValueError("Request missing parameter 'poller'")

    pollers = []

    for pollername in req.args['poller']:
        try:
            source = change_svc.getServiceNamed(pollername)
        except KeyError:
            raise ValueError("No such change source '%s'" % pollername)

        if not isinstance(source, PollingChangeSource):
            raise ValueError("No such polling change source '%s'" % pollername)

        pollers.append(source)

    for p in pollers:
        source.doPoll()

    return [], None


