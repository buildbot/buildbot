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

# note that this cannot be run in tests for code coverage, as it requires a
# different reactor than the default

from buildbot.clients import text

def statuslog(config):
    master = config.get('master')
    passwd = config.get('passwd')
    username = config.get('username')
    c = text.TextClient(master, username=username, passwd=passwd)
    c.run()
    return 0
