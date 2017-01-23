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
from __future__ import print_function

import os

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest


class FuzzTestCase(unittest.TestCase):

    # run each test case for 10s
    FUZZ_TIME = 10

    @defer.inlineCallbacks
    def test_fuzz(self):
        # note that this will loop if do_fuzz doesn't take long enough
        endTime = reactor.seconds() + self.FUZZ_TIME
        while reactor.seconds() < endTime:
            yield self.do_fuzz(endTime)

    # delete this test case entirely if fuzzing is not enabled
    if 'BUILDBOT_FUZZ' not in os.environ:
        del test_fuzz
