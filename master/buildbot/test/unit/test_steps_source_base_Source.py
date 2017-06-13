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

from buildbot.steps.source import Source
from buildbot.test.util import sourcesteps
from buildbot.test.util import steps


class TestSource(sourcesteps.SourceStepMixin, unittest.SynchronousTestCase):

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
            patch='patch'
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
            patch='patch'
        )
        step.branch = 'branch'
        step.startVC = mock.Mock()

        step.startStep(mock.Mock())

        self.assertEqual(
            step.startVC.call_args, (('other-branch', 'revision', 'patch'), {}))

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

        self.assertEqual(step.describe(), ['updating'])
        self.assertEqual(step.name, Source.name)

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('',))

        self.assertEqual(step.description, ['updating'])

    def test_start_with_codebase(self):
        step = self.setupStep(Source(codebase='codebase'))
        step.branch = 'branch'
        step.startVC = mock.Mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        self.assertEqual(step.describe(), ['updating', 'codebase'])
        step.name = self.successResultOf(step.build.render(step.name))
        self.assertEqual(step.name, Source.name + "-codebase")

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('codebase',))

        self.assertEqual(step.describe(True), ['update', 'codebase'])

    def test_start_with_codebase_and_descriptionSuffix(self):
        step = self.setupStep(Source(codebase='my-code',
                                     descriptionSuffix='suffix'))
        step.branch = 'branch'
        step.startVC = mock.Mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        self.assertEqual(step.describe(), ['updating', 'suffix'])
        step.name = self.successResultOf(step.build.render(step.name))
        self.assertEqual(step.name, Source.name + "-my-code")

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('my-code',))

        self.assertEqual(step.describe(True), ['update', 'suffix'])


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


class AttrGroup(Source):

    def other_method(self):
        pass

    def mode_full(self):
        pass

    def mode_incremental(self):
        pass


class TestSourceAttrGroup(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_attrgroup_hasattr(self):
        step = AttrGroup()
        self.assertTrue(step._hasAttrGroupMember('mode', 'full'))
        self.assertTrue(step._hasAttrGroupMember('mode', 'incremental'))
        self.assertFalse(step._hasAttrGroupMember('mode', 'nothing'))

    def test_attrgroup_getattr(self):
        step = AttrGroup()
        self.assertEqual(step._getAttrGroupMember('mode', 'full'),
                         step.mode_full)
        self.assertEqual(step._getAttrGroupMember('mode', 'incremental'),
                         step.mode_incremental)
        self.assertRaises(AttributeError,
                          step._getAttrGroupMember, 'mode', 'nothing')

    def test_attrgroup_listattr(self):
        step = AttrGroup()
        self.assertEqual(sorted(step._listAttrGroupMembers('mode')),
                         ['full', 'incremental'])
