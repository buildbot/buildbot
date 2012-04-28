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

import weakref
from twisted.internet import defer
from buildbot.test.fake import fakedb
from buildbot.test.fake.pbmanager import FakePBManager
from buildbot import config
import mock

class FakeCache(object):
    """Emulate an L{AsyncLRUCache}, but without any real caching.  This
    I{does} do the weakref part, to catch un-weakref-able objects."""
    def __init__(self, name, miss_fn):
        self.name = name
        self.miss_fn = miss_fn

    def get(self, key, **kwargs):
        d = self.miss_fn(key, **kwargs)
        def mkref(x):
            if x is not None:
                weakref.ref(x)
            return x
        d.addCallback(mkref)
        return d


class FakeMaster(mock.Mock):
    """
    Create a fake Master instance: a Mock with some convenience
    implementations:

    - Non-caching implementation for C{self.caches}
    """

    def __init__(self, master_id=fakedb.FakeBuildRequestsComponent.MASTER_ID):
        mock.Mock.__init__(self, name="fakemaster")
        self._master_id = master_id
        self.config = config.MasterConfig()
        self.caches.get_cache = FakeCache
        self.pbmanager = FakePBManager()

    def getObjectId(self):
        return defer.succeed(self._master_id)

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)

# Leave this alias, in case we want to add more behavior later
make_master = FakeMaster
