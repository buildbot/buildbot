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


def make_master(master_id=fakedb.FakeBuildRequestsComponent.MASTER_ID):
    """
    Create a fake Master instance: a Mock with some convenience
    implementations:

    - Non-caching implementation for C{self.caches}
    """

    fakemaster = mock.Mock(name="fakemaster")

    # set up caches
    fakemaster.caches.get_cache = FakeCache

    # and a getObjectId method
    fakemaster.getObjectId = (lambda : defer.succeed(master_id))

    return fakemaster
