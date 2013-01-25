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

from zope.interface import implements
from twisted.python import log
from twisted.internet import defer
from twisted.application import service
from buildbot import interfaces, config, util
from buildbot.process import metrics

class ChangeManager(config.ReconfigurableServiceMixin, service.MultiService):
    """
    This is the master-side service which receives file change notifications
    from version-control systems.

    It is a Twisted service, which has instances of
    L{buildbot.interfaces.IChangeSource} as child services. These are added by
    the master with C{addSource}.
    """

    implements(interfaces.IEventSource)

    name = "changemanager"

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('change_manager')
        self.master = master

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        timer = metrics.Timer("ChangeManager.reconfigService")
        timer.start()

        removed, added = util.diffSets(
                set(self),
                new_config.change_sources)

        if removed or added:
            log.msg("adding %d new changesources, removing %d" %
                    (len(added), len(removed)))

            for src in removed:
                yield defer.maybeDeferred(
                        src.disownServiceParent)
                src.master = None

            for src in added:
                src.master = self.master
                src.setServiceParent(self)

        num_sources = len(list(self))
        assert num_sources == len(new_config.change_sources)
        metrics.MetricCountEvent.log("num_sources", num_sources, absolute=True)

        # reconfig any newly-added change sources, as well as existing
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                        new_config)

        timer.stop()
