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

from twisted import version
from twisted.python import log
from twisted.python import versions
from twisted.spread import pb
from twisted.spread.interfaces import IJellyable


def patch():
    if version < versions.Version('twisted', 8, 2, 0):
        return  # too old
    log.msg("Applying patch for http://twistedmatrix.com/trac/ticket/5079")
    if not hasattr(pb, '_JellyableAvatarMixin'):
        log.msg("..patch not applicable; please file a bug at buildbot.net")
    else:
        pb._JellyableAvatarMixin._cbLogin = _fixed_cbLogin


def _fixed_cbLogin(self, xxx_todo_changeme):
    """
    Ensure that the avatar to be returned to the client is jellyable and
    set up disconnection notification to call the realm's logout object.
    """
    (interface, avatar, logout) = xxx_todo_changeme
    if not IJellyable.providedBy(avatar):
        avatar = pb.AsReferenceable(avatar, "perspective")

    puid = avatar.processUniqueID()

    # only call logout once, whether the connection is dropped (disconnect)
    # or a logout occurs (cleanup), and be careful to drop the reference to
    # it in either case
    logout = [logout]

    def maybeLogout():
        if not logout:
            return
        fn = logout[0]
        del logout[0]
        fn()
    self.broker._localCleanup[puid] = maybeLogout
    self.broker.notifyOnDisconnect(maybeLogout)

    return avatar
