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

import pprint


class FakeWorkerForBuilder(object):

    """
    Simulates a WorkerForBuilder, but just records the updates from sendUpdate
    in its updates attribute.  Call show() to get a pretty-printed string
    showing the updates.  Set debug to True to show updates as they happen.
    """
    debug = False

    def __init__(self, basedir="/workerbuilder/basedir"):
        self.updates = []
        self.basedir = basedir
        self.unicode_encoding = 'utf-8'

    def sendUpdate(self, data):
        if self.debug:
            print("FakeWorkerForBuilder.sendUpdate", data)
        self.updates.append(data)

    def show(self):
        return pprint.pformat(self.updates)
