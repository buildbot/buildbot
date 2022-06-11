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


import re

from twisted.python import log


class LoggingMixin:

    def setUpLogging(self):
        self._logEvents = []
        log.addObserver(self._logEvents.append)
        self.addCleanup(log.removeObserver, self._logEvents.append)

    def logContainsMessage(self, regexp):
        r = re.compile(regexp)
        for event in self._logEvents:
            msg = log.textFromEventDict(event)
            if msg is not None:
                assert not msg.startswith("Unable to format event"), msg
            if msg is not None and r.search(msg):
                return True
        return False

    def assertLogged(self, regexp):
        if not self.logContainsMessage(regexp):
            lines = [log.textFromEventDict(e) for e in self._logEvents]
            self.fail(f"{repr(regexp)} not matched in log output.\n{lines} ")

    def assertNotLogged(self, regexp):
        if self.logContainsMessage(regexp):
            lines = [log.textFromEventDict(e) for e in self._logEvents]
            self.fail(f"{repr(regexp)} matched in log output.\n{lines} ")

    def assertWasQuiet(self):
        self.assertEqual([
            log.textFromEventDict(event) for event in self._logEvents], [])
