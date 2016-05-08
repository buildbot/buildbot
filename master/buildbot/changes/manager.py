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

from twisted.internet import defer
from twisted.python import log
from zope.interface import implements

from buildbot import interfaces
from buildbot import util
from buildbot.process import metrics
from buildbot.util import service


class ChangeManager(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    """
    This is the master-side service which receives file change notifications
    from version-control systems.

    It is a Twisted service, which has instances of
    L{buildbot.interfaces.IChangeSource} as child services. These are added by
    the master with C{addSource}.
    """

    implements(interfaces.IEventSource)

    name = "change_manager"

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        timer = metrics.Timer(
            "ChangeManager.reconfigServiceWithBuildbotConfig")
        timer.start()

        removed, added = util.diffSets(
            set(self),
            new_config.change_sources)

        if removed or added:
            log.msg("adding %d new changesources, removing %d" %
                    (len(added), len(removed)))

            for src in removed:
                yield src.deactivate()
                yield defer.maybeDeferred(
                    src.disownServiceParent)

            for src in added:
                yield src.setServiceParent(self)

        num_sources = len(list(self))
        assert num_sources == len(new_config.change_sources)
        metrics.MetricCountEvent.log("num_sources", num_sources, absolute=True)

        # reconfig any newly-added change sources, as well as existing
        yield service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                   new_config)

        timer.stop()
