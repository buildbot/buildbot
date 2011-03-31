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

from mock import Mock

from twisted.internet import defer

class MockRequest(Mock):
    """
    A fake Twisted Web Request object, including some pointers to the
    buildmaster and an addChange method on that master which will append its
    arguments to self.addedChanges.
    """
    def __init__(self, args={}):
        self.args = args
        self.site = Mock()
        self.site.buildbot_service = Mock()
        master = self.site.buildbot_service.master = Mock()

        self.addedChanges = []
        def addChange(**kwargs):
            self.addedChanges.append(kwargs)
            return defer.succeed(Mock())
        master.addChange = addChange

        Mock.__init__(self)
