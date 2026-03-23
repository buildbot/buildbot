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

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process import results
from buildbot.steps.source import Source
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import sourcesteps

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


class OldStyleSourceStep(Source):
    def startVC(self) -> None:
        self.finished(results.SUCCESS)  # type: ignore[attr-defined]


class TestSource(sourcesteps.SourceStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def setup_deferred_mock(self) -> Callable[..., int]:
        m = mock.Mock()

        def wrapper(*args: Any, **kwargs: Any) -> int:
            m(*args, **kwargs)
            return results.SUCCESS

        wrapper.mock = m  # type: ignore[attr-defined]
        return wrapper

    def test_start_alwaysUseLatest_True(self) -> None:
        step = self.setup_step(
            Source(alwaysUseLatest=True),
            {
                'branch': 'other-branch',
                'revision': 'revision',
            },
            patch='patch',
        )
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()

        step.startStep(mock.Mock())

        self.assertEqual(step.run_vc.mock.call_args, (('branch', None, None), {}))

    def test_start_alwaysUseLatest_False(self) -> None:
        step = self.setup_step(
            Source(),
            {
                'branch': 'other-branch',
                'revision': 'revision',
            },
            patch='patch',
        )
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()

        step.startStep(mock.Mock())

        self.assertEqual(step.run_vc.mock.call_args, (('other-branch', 'revision', 'patch'), {}))

    def test_start_alwaysUseLatest_False_binary_patch(self) -> None:
        args = {
            'branch': 'other-branch',
            'revision': 'revision',
        }
        step = self.setup_step(Source(), args, patch=(1, b'patch\xf8'))
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()

        step.startStep(mock.Mock())

        self.assertEqual(
            step.run_vc.mock.call_args, (('other-branch', 'revision', (1, b'patch\xf8')), {})
        )

    def test_start_alwaysUseLatest_False_no_branch(self) -> None:
        step = self.setup_step(Source())
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()

        step.startStep(mock.Mock())

        self.assertEqual(step.run_vc.mock.call_args, (('branch', None, None), {}))

    def test_start_no_codebase(self) -> None:
        step = self.setup_step(Source())
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        self.assertEqual(step.getCurrentSummary(), {'step': 'updating'})
        self.assertEqual(step.name, Source.name)

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('',))

        self.assertEqual(step.getCurrentSummary(), {'step': 'updating'})

    @defer.inlineCallbacks
    def test_start_with_codebase(self) -> InlineCallbacksType[None]:
        step = self.setup_step(Source(codebase='codebase'))
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        self.assertEqual(step.getCurrentSummary(), {'step': 'updating codebase'})
        step.name = yield step.build.render(step.name)
        self.assertEqual(step.name, Source.name + "-codebase")  # type: ignore[operator]

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('codebase',))

        self.assertEqual(
            step.getResultSummary(), {'step': 'Codebase codebase not in build codebase (failure)'}
        )

    @defer.inlineCallbacks
    def test_start_with_codebase_and_descriptionSuffix(self) -> InlineCallbacksType[None]:
        step = self.setup_step(Source(codebase='my-code', descriptionSuffix='suffix'))  # type: ignore[arg-type]
        step.branch = 'branch'
        step.run_vc = self.setup_deferred_mock()
        step.build.getSourceStamp = mock.Mock()
        step.build.getSourceStamp.return_value = None

        self.assertEqual(step.getCurrentSummary(), {'step': 'updating suffix'})
        step.name = yield step.build.render(step.name)
        self.assertEqual(step.name, Source.name + "-my-code")  # type: ignore[operator]

        step.startStep(mock.Mock())
        self.assertEqual(step.build.getSourceStamp.call_args[0], ('my-code',))

        self.assertEqual(
            step.getResultSummary(), {'step': 'Codebase my-code not in build suffix (failure)'}
        )

    def test_old_style_source_step_throws_exception(self) -> None:
        step = self.setup_step(OldStyleSourceStep())

        step.startStep(mock.Mock())

        self.expect_outcome(result=results.EXCEPTION)
        self.flushLoggedErrors(NotImplementedError)


class TestSourceDescription(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_constructor_args_strings(self) -> None:
        step = Source(
            workdir='build',
            description='svn update (running)',  # type: ignore[arg-type]
            descriptionDone='svn update',  # type: ignore[arg-type]
        )
        self.assertEqual(step.description, ['svn update (running)'])
        self.assertEqual(step.descriptionDone, ['svn update'])

    def test_constructor_args_lists(self) -> None:
        step = Source(
            workdir='build',
            description=['svn', 'update', '(running)'],
            descriptionDone=['svn', 'update'],
        )
        self.assertEqual(step.description, ['svn', 'update', '(running)'])
        self.assertEqual(step.descriptionDone, ['svn', 'update'])


class AttrGroup(Source):
    def other_method(self) -> None:
        pass

    def mode_full(self) -> None:
        pass

    def mode_incremental(self) -> None:
        pass


class TestSourceAttrGroup(sourcesteps.SourceStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_attrgroup_hasattr(self) -> None:
        step = AttrGroup()
        self.assertTrue(step._hasAttrGroupMember('mode', 'full'))
        self.assertTrue(step._hasAttrGroupMember('mode', 'incremental'))
        self.assertFalse(step._hasAttrGroupMember('mode', 'nothing'))

    def test_attrgroup_getattr(self) -> None:
        step = AttrGroup()
        self.assertEqual(step._getAttrGroupMember('mode', 'full'), step.mode_full)
        self.assertEqual(step._getAttrGroupMember('mode', 'incremental'), step.mode_incremental)
        with self.assertRaises(AttributeError):
            step._getAttrGroupMember('mode', 'nothing')

    def test_attrgroup_listattr(self) -> None:
        step = AttrGroup()
        self.assertEqual(sorted(step._listAttrGroupMembers('mode')), ['full', 'incremental'])
