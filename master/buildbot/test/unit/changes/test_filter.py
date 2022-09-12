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

import re

from parameterized import parameterized

from twisted.trial import unittest

from buildbot.changes.filter import ChangeFilter
from buildbot.test.fake.change import Change


class TestChangeFilter(unittest.TestCase):
    def test_filter_change_filter_fn(self):
        f = ChangeFilter(filter_fn=lambda ch: ch.x > 3)
        self.assertFalse(f.filter_change(Change(x=2)))
        self.assertTrue(f.filter_change(Change(x=4)))

        self.assertEqual(repr(f), "<ChangeFilter on <lambda>()>")

    test_cases = [
        (
            "match",
            Change(project="p", codebase="c", repository="r", category="ct", branch="b"),
            True,
        ),
        (
            "not_project",
            Change(project="p0", codebase="c", repository="r", category="ct", branch="b"),
            False,
        ),
        (
            "not_codebase",
            Change(project="p", codebase="c0", repository="r", category="ct", branch="b"),
            False,
        ),
        (
            "not_repository",
            Change(project="p", codebase="c", repository="r0", category="ct", branch="b"),
            False,
        ),
        (
            "not_category",
            Change(project="p", codebase="c", repository="r", category="ct0", branch="b"),
            False,
        ),
        (
            "not_branch",
            Change(project="p", codebase="c", repository="r", category="ct", branch="b0"),
            False,
        ),
    ]

    @parameterized.expand(test_cases)
    def test_eq(self, name, change, expected):
        f = ChangeFilter(project="p", codebase="c", repository="r", category="ct", branch="b")
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_eq_list(self, name, change, expected):
        f = ChangeFilter(
            project=["p", "p9"],
            codebase=["c", "c9"],
            repository=["r", "r9"],
            category=["ct", "ct9"],
            branch=["b", "b9"],
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_not_eq(self, name, change, expected):
        f = ChangeFilter(
            project_not_eq="p0",
            codebase_not_eq="c0",
            repository_not_eq="r0",
            category_not_eq="ct0",
            branch_not_eq="b0",
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_not_eq_list(self, name, change, expected):
        f = ChangeFilter(
            project_not_eq=["p0", "p1"],
            codebase_not_eq=["c0", "c1"],
            repository_not_eq=["r0", "r1"],
            category_not_eq=["ct0", "ct1"],
            branch_not_eq=["b0", "b1"],
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_re(self, name, change, expected):
        f = ChangeFilter(
            project_re="^p$",
            codebase_re="^c$",
            repository_re="^r$",
            category_re="^ct$",
            branch_re="^b$",
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_re_list(self, name, change, expected):
        f = ChangeFilter(
            project_re=["^p$", "^p1$"],
            codebase_re=["^c$", "^c1$"],
            repository_re=["^r$", "^r1$"],
            category_re=["^ct$", "^ct1$"],
            branch_re=["^b$", "^b1$"],
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_not_re(self, name, change, expected):
        f = ChangeFilter(
            project_not_re="^p0$",
            codebase_not_re="^c0$",
            repository_not_re="^r0$",
            category_not_re="^ct0$",
            branch_not_re="^b0$",
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_not_re_list(self, name, change, expected):
        f = ChangeFilter(
            project_not_re=["^p0$", "^p1$"],
            codebase_not_re=["^c0$", "^c1$"],
            repository_not_re=["^r0$", "^r1$"],
            category_not_re=["^ct0$", "^ct1$"],
            branch_not_re=["^b0$", "^b1$"],
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_re_pattern(self, name, change, expected):
        f = ChangeFilter(
            project_re=re.compile("^p$"),
            codebase_re=re.compile("^c$"),
            repository_re=re.compile("^r$"),
            category_re=re.compile("^ct$"),
            branch_re=re.compile("^b$"),
        )
        self.assertEqual(f.filter_change(change), expected)

    @parameterized.expand(test_cases)
    def test_fn(self, name, change, expected):
        f = ChangeFilter(
            project_fn=lambda p: p == "p",
            codebase_fn=lambda p: p == "c",
            repository_fn=lambda p: p == "r",
            category_fn=lambda p: p == "ct",
            branch_fn=lambda p: p == "b",
        )
        self.assertEqual(f.filter_change(change), expected)

        self.assertEqual(
            repr(f),
            "<ChangeFilter on <lambda>(project) and <lambda>(codebase) and "
            "<lambda>(repository) and <lambda>(category) and <lambda>(branch)>",
        )

    def test_filter_change_filt_branch_list_None(self):
        f = ChangeFilter(branch=["mybr", None])
        self.assertTrue(f.filter_change(Change(branch="mybr")))
        self.assertTrue(f.filter_change(Change(branch=None)))
        self.assertFalse(f.filter_change(Change(branch="misc")))

    def test_filter_change_branch_re(self):  # regression - see #927
        f = ChangeFilter(branch_re="^t.*")
        self.assertTrue(f.filter_change(Change(branch="trunk")))
        self.assertFalse(f.filter_change(Change(branch="development")))
        self.assertFalse(f.filter_change(Change(branch=None)))

    def test_filter_change_combination(self):
        f = ChangeFilter(project="p", repository="r", branch="b", category="c", codebase="cb")
        self.assertFalse(
            f.filter_change(Change(project="x", repository="x", branch="x", category="x"))
        )
        self.assertFalse(
            f.filter_change(Change(project="p", repository="r", branch="b", category="x"))
        )
        self.assertFalse(
            f.filter_change(Change(project="p", repository="r", branch="b", category="c"))
        )
        self.assertTrue(
            f.filter_change(
                Change(project="p", repository="r", branch="b", category="c", codebase="cb")
            )
        )

    def test_filter_change_combination_filter_fn(self):
        f = ChangeFilter(
            project="p",
            repository="r",
            branch="b",
            category="c",
            filter_fn=lambda c: c.ff,
        )
        self.assertFalse(
            f.filter_change(Change(project="x", repository="x", branch="x", category="x", ff=False))
        )
        self.assertFalse(
            f.filter_change(Change(project="p", repository="r", branch="b", category="c", ff=False))
        )
        self.assertFalse(
            f.filter_change(Change(project="x", repository="x", branch="x", category="x", ff=True))
        )
        self.assertTrue(
            f.filter_change(Change(project="p", repository="r", branch="b", category="c", ff=True))
        )

    def test_filter_props(self):
        f = ChangeFilter(property_eq={"event.type": "ref-updated"})
        self.assertTrue(f.filter_change(Change(properties={"event.type": "ref-updated"})))
        self.assertFalse(f.filter_change(Change(properties={"event.type": "patch-uploaded"})))
        self.assertFalse(f.filter_change(Change(properties={})))

        f = ChangeFilter(property_re={"event.type": "^ref-updated$"})
        self.assertTrue(f.filter_change(Change(properties={"event.type": "ref-updated"})))
        self.assertFalse(f.filter_change(Change(properties={"event.type": "patch-uploaded"})))
        self.assertFalse(f.filter_change(Change(properties={})))
