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
from buildbot.test.util import steps, sourcesteps

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

    def test_start_no_codebase(self):
        step = self.setupStep(Source())
        step.branch = 'branch'
        step.startVC = mock.Mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('',))
        
    def test_start_with_codebase(self):
        step = self.setupStep(Source(codebase='codebase'))
        step.branch = 'branch'
        step.startVC = mock.Mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('codebase',))        

class TestSourceDescription(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_constructor_args_strings(self):
        step = Source(workdir='build',
                      description='svn update (running)',
                      descriptionDone='svn update')
        self.assertEqual(step.description, ['svn update (running)'])
        self.assertEqual(step.descriptionDone, ['svn update'])

    def test_constructor_args_lists(self):
        step = Source(workdir='build',
                      description=['svn', 'update', '(running)'],
                      descriptionDone=['svn', 'update'])
        self.assertEqual(step.description, ['svn', 'update', '(running)'])
        self.assertEqual(step.descriptionDone, ['svn', 'update'])
