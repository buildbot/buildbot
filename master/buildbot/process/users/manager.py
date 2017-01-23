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

from twisted.application import service
from twisted.internet import defer

from buildbot.util import service as util_service


class UserManagerManager(util_service.ReconfigurableServiceMixin,
                         service.MultiService):
    # this class manages a fleet of user managers; hence the name..

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('user_manager_manager')
        self.master = master

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        # this is easy - kick out all of the old managers, and add the
        # new ones.

        # pylint: disable=cell-var-from-loop
        for mgr in list(self):
            yield defer.maybeDeferred(lambda:
                                      mgr.disownServiceParent())

        for mgr in new_config.user_managers:
            yield mgr.setServiceParent(self)

        # reconfig any newly-added change sources, as well as existing
        yield util_service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                        new_config)
