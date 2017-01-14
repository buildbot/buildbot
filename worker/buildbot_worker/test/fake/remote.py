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

from twisted.internet import defer


class FakeRemote(object):

    """
    Wrap a local object to make it look like it's remote
    """

    def __init__(self, original, method_prefix="remote_"):
        self.original = original
        self.method_prefix = method_prefix

    def callRemote(self, meth, *args, **kwargs):
        fn = getattr(self.original, self.method_prefix + meth)
        return defer.maybeDeferred(fn, *args, **kwargs)

    def notifyOnDisconnect(self, what):
        pass

    def dontNotifyOnDisconnect(self, what):
        pass
