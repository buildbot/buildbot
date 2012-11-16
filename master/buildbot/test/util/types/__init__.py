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

from twisted.python.reflect import namedObject

def _call(name, *args):
    if not name:
        return # temporary
    name = 'buildbot.test.util.types.' + name
    obj = namedObject(name)
    return obj(*args)

_messageVerifiers = {
    'change' : 'changes.verifyMessage',
    'buildset' : 'buildsets.verifyMessage',
    'buildrequest' : None,
    'master' : 'masters.verifyMessage',
    'builder' : 'builders.verifyMessage',
}
def verifyMessage(testcase, routingKey, message):
    return _call(_messageVerifiers[routingKey[0]], testcase, routingKey, message)

_dbVerifiers = {
    'bsdict' : 'buildsets.verifyDbDict',
    'chdict' : 'changes.verifyDbDict',
    'bsdict' : 'buildsets.verifyDbDict',
    'masterdict' : 'masters.verifyDbDict',
    'schedulerdict' : 'schedulers.verifyDbDict',
    'builderdict' : 'builders.verifyDbDict',
}
def verifyDbDict(testcase, type, value):
    return _call(_dbVerifiers[type], testcase, type, value)

_dataVerifiers = {
    'buildset' : 'buildsets.verifyData',
    'change' : 'changes.verifyData',
    'master' : 'masters.verifyData',
    'builder' : 'builders.verifyData',
}
def verifyData(testcase, type, options, value):
    return _call(_dataVerifiers[type], testcase, type, options, value)
