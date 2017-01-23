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
from __future__ import division
from __future__ import print_function

from twisted.internet import defer

from buildbot.clients import usersclient
from buildbot.process.users import users
from buildbot.util import in_reactor


@in_reactor
@defer.inlineCallbacks
def user(config):

    master = config.get('master')
    op = config.get('op')
    username = config.get('username')
    passwd = config.get('passwd')
    master, port = master.split(":")
    port = int(port)
    bb_username = config.get('bb_username')
    bb_password = config.get('bb_password')
    if bb_username or bb_password:
        bb_password = users.encrypt(bb_password)
    info = config.get('info')
    ids = config.get('ids')

    # find identifier if op == add
    if info and op == 'add':
        for user in info:
            user['identifier'] = sorted(user.values())[0]

    uc = usersclient.UsersClient(master, username, passwd, port)
    output = yield uc.send(op, bb_username, bb_password, ids, info)
    if output:
        print(output)

    defer.returnValue(0)
