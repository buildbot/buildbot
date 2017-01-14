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

from twisted.trial import unittest

from buildbot.clients import tryclient
from buildbot.scripts import trycmd


class TestStatusLog(unittest.TestCase):

    def test_trycmd(self):
        Try = mock.Mock()
        self.patch(tryclient, 'Try', Try)
        inst = Try.return_value = mock.Mock(name='Try-instance')

        rc = trycmd.trycmd(dict(cfg=1))

        Try.assert_called_with(dict(cfg=1))
        inst.run.assert_called_with()
        self.assertEqual(rc, 0)
