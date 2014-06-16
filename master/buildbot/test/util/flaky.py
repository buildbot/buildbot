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

import os
envVar = 'RUN_FLAKY_TESTS'


def flaky(bugNumber):
    def wrap(fn):
        if not os.environ.get(envVar):
            fn.skip = ("Flaky test (http://trac.buildbot.net/ticket/%d) "
                       "- set $%s to run anyway" % (bugNumber, envVar))
        return fn
    return wrap
