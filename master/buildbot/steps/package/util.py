# This program is free software; you can
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
# Portions Copyright Buildbot Team Members
# Portions Copyright Marius Rieder <marius.rieder@durchmesser.ch>

from __future__ import absolute_import
from __future__ import print_function

from buildbot.process import logobserver


class WEObserver(logobserver.LogLineObserver):

    def __init__(self):
        logobserver.LogLineObserver.__init__(self)
        self.warnings = []
        self.errors = []

    def outLineReceived(self, line):
        if line.startswith('W: '):
            self.warnings.append(line)
        elif line.startswith('E: '):
            self.errors.append(line)
