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

from twisted.trial import unittest

def add_debugging_monkeypatches():
    """
    DO NOT CALL THIS DIRECTLY

    This adds a few "harmless" monkeypatches which make it easier to debug
    failing tests.  It is called automatically by buildbot.test.__init__.
    """
    from twisted.application.service import Service
    old_startService = Service.startService
    old_stopService = Service.stopService
    def startService(self):
        assert not self.running
        return old_startService(self)
    def stopService(self):
        assert self.running
        return old_stopService(self)
    Service.startService = startService
    Service.stopService = stopService

    # make unittest.TestCase have a patch method, even if it just skips
    # the test.
    def nopatch(self, *args):
        raise unittest.SkipTest('unittest.patch is not available')
    if not hasattr(unittest.TestCase, 'patch'):
        unittest.TestCase.patch = nopatch
