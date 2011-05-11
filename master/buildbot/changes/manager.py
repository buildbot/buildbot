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
from twisted.internet import defer
from twisted.application import service

from buildbot import interfaces

class ChangeManager(service.MultiService):
    """
    This is the master-side service which receives file change notifications
    from version-control systems.

    It is a Twisted service, which has instances of
    L{buildbot.interfaces.IChangeSource} as child services. These are added by
    the master with C{addSource}.
    """

    implements(interfaces.IEventSource)

    lastPruneChanges = None
    name = "changemanager"

    def __init__(self):
        service.MultiService.__init__(self)
        self.master = None
        self.lastPruneChanges = 0

    def startService(self):
        service.MultiService.startService(self)
        self.master = self.parent

    def addSource(self, source):
        assert interfaces.IChangeSource.providedBy(source)
        assert service.IService.providedBy(source)
        source.master = self.master
        source.setServiceParent(self)

    def removeSource(self, source):
        assert source in self
        d = defer.maybeDeferred(source.disownServiceParent)
        def unset_master(x):
            source.master = None
            return x
        d.addBoth(unset_master)
        return d
