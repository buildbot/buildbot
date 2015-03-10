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
"""
Tests for buildbot.status.builder module.
"""
from buildbot.status import builder
from buildbot.test.fake import fakemaster
from twisted.trial import unittest


class TestBuilderStatus(unittest.TestCase):
    """
    Unit tests for BuilderStatus.
    """

    def makeBuilderStatus(self):
        """
        Return a new BuilderStatus.
        """

        return builder.BuilderStatus(
            buildername='testing-builder',
            tags=None,
            master=fakemaster.make_master(),
            description=None)

    def test_matchesAnyTag_no_tags(self):
        """
        Return False when builder has no tags.
        """
        sut = self.makeBuilderStatus()

        self.assertFalse(sut.matchesAnyTag(set()))
        self.assertFalse(sut.matchesAnyTag(set(('any-tag', 'tag'))))

    def test_matchesAnyTag_no_match(self):
        """
        Return False when requested tags don't match.
        """
        sut = self.makeBuilderStatus()
        sut.tags = set('one')

        self.assertFalse(sut.matchesAnyTag(set()))
        self.assertFalse(sut.matchesAnyTag(set(('no-such-tag',))))
        self.assertFalse(sut.matchesAnyTag(set(('other-tag', 'tag'))))

    def test_matchesAnyTag_with_match(self):
        """
        Return True when at least one of the requested tags match.
        """
        sut = self.makeBuilderStatus()
        sut.tags = set(('one', 'two'))

        self.assertTrue(sut.matchesAnyTag(set(('two',))))
        self.assertTrue(sut.matchesAnyTag(set(('two', 'one'))))
