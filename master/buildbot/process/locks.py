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


@defer.inlineCallbacks
def get_real_locks_from_accesses_raw(locks, props, builder, workerforbuilder, config_version):
    workername = workerforbuilder.worker.workername

    if props is not None:
        locks = yield props.render(locks)

    if not locks:
        return []

    locks = yield builder.botmaster.getLockFromLockAccesses(locks, config_version)
    return [(l.getLockForWorker(workername), a) for l, a in locks]


def get_real_locks_from_accesses(locks, build):
    return get_real_locks_from_accesses_raw(
        locks, build, build.builder, build.workerforbuilder, build.config_version
    )
