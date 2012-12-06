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


import webbrowser,os
from twisted.internet import reactor, defer
from buildbot.test.fake import fakemaster

@defer.inlineCallbacks
def _uitestserver(config):
    master = yield fakemaster.make_master_for_uitest(int(config['port']))
    if "DISPLAY" in os.environ:
        webbrowser.open(master.config.www['url']+"app/base/bb/tests/runner.html")

def uitestserver(config):
    def async():
        return _uitestserver(config)
    reactor.callWhenRunning(async)
    # unlike in_reactor, we dont stop until CTRL-C
    reactor.run()
