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

import mock
from twisted.trial import unittest

from buildbot.steps.source import Source
from buildbot.test.util import sourcesteps

class TestSource(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_start_alwaysUseLatest_True(self):
        step = self.setupStep(Source(alwaysUseLatest=True),
                {
                    'branch': 'other-branch',
                    'revision': 'revision',
                },
                patch = 'patch'
                )
        step.branch = 'branch'
        step.startVC = mock.Mock()

        step.startStep(mock.Mock())

        self.assertEqual(step.startVC.call_args, (('branch', None, None), {}))

    def test_start_alwaysUseLatest_False(self):
        step = self.setupStep(Source(),
                {
                    'branch': 'other-branch',
                    'revision': 'revision',
                },
                patch = 'patch'
                )
        step.branch = 'branch'
        step.startVC = mock.Mock()

        step.startStep(mock.Mock())

        self.assertEqual(step.startVC.call_args, (('other-branch', 'revision', 'patch'), {}))

    def test_start_alwaysUseLatest_False_no_branch(self):
        step = self.setupStep(Source())
        step.branch = 'branch'
        step.startVC = mock.Mock()

        step.startStep(mock.Mock())

        self.assertEqual(step.startVC.call_args, (('branch', None, None), {}))
