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

import mock

from twisted.internet import defer
from twisted.python import failure
from twisted.trial import unittest

from buildbot.mq import base


class QueueRef(unittest.TestCase):

    def test_success(self):
        cb = mock.Mock(name='cb')
        qref = base.QueueRef(cb)

        qref.invoke('rk', 'd')

        cb.assert_called_with('rk', 'd')

    def test_success_deferred(self):
        cb = mock.Mock(name='cb')
        cb.return_value = defer.succeed(None)
        qref = base.QueueRef(cb)

        qref.invoke('rk', 'd')

        cb.assert_called_with('rk', 'd')

    def test_exception(self):
        cb = mock.Mock(name='cb')
        cb.side_effect = RuntimeError('oh noes!')
        qref = base.QueueRef(cb)

        qref.invoke('rk', 'd')

        cb.assert_called_with('rk', 'd')
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    def test_failure(self):
        cb = mock.Mock(name='cb')
        cb.return_value = defer.fail(failure.Failure(RuntimeError('oh noes!')))
        qref = base.QueueRef(cb)

        qref.invoke('rk', 'd')

        cb.assert_called_with('rk', 'd')
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
