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

from twisted.trial import unittest

from buildbot.changes.filter import ChangeFilter
from buildbot.test.fake.change import Change


class TestChangeFilter(unittest.TestCase):
    def test_filter_change_filter_fn(self):
        f = ChangeFilter(filter_fn=lambda ch: ch.x > 3)
        self.assertFalse(f.filter_change(Change(x=2)))
        self.assertTrue(f.filter_change(Change(x=4)))

    def test_filter_change_filt_str(self):
        f = ChangeFilter(project="myproj")
        self.assertFalse(f.filter_change(Change(project="yourproj")))
        self.assertTrue(f.filter_change(Change(project="myproj")))

    def test_filter_change_filt_list(self):
        f = ChangeFilter(repository=["vc://a", "vc://b"])
        self.assertTrue(f.filter_change(Change(repository="vc://a")))
        self.assertTrue(f.filter_change(Change(repository="vc://b")))
        self.assertFalse(f.filter_change(Change(repository="vc://c")))
        self.assertFalse(f.filter_change(Change(repository=None)))

    def test_filter_change_filt_list_None(self):
        f = ChangeFilter(branch=["mybr", None])
        self.assertTrue(f.filter_change(Change(branch="mybr")))
        self.assertTrue(f.filter_change(Change(branch=None)))
        self.assertFalse(f.filter_change(Change(branch="misc")))

    def test_filter_change_filt_re(self):
        f = ChangeFilter(category_re="^a.*")
        self.assertTrue(f.filter_change(Change(category="albert")))
        self.assertFalse(f.filter_change(Change(category="boris")))

    def test_filter_change_branch_re(self):  # regression - see #927
        f = ChangeFilter(branch_re="^t.*")
        self.assertTrue(f.filter_change(Change(branch="trunk")))
        self.assertFalse(f.filter_change(Change(branch="development")))
        self.assertFalse(f.filter_change(Change(branch=None)))

    def test_filter_change_filt_re_compiled(self):
        f = ChangeFilter(category_re=re.compile("^b.*", re.I))
        self.assertFalse(f.filter_change(Change(category="albert")))
        self.assertTrue(f.filter_change(Change(category="boris")))
        self.assertTrue(f.filter_change(Change(category="Bruce")))

    def test_filter_change_combination(self):
        f = ChangeFilter(project='p', repository='r', branch='b', category='c', codebase='cb')
        self.assertFalse(f.filter_change(
            Change(project='x', repository='x', branch='x', category='x')))
        self.assertFalse(f.filter_change(
            Change(project='p', repository='r', branch='b', category='x')))
        self.assertFalse(f.filter_change(
            Change(project='p', repository='r', branch='b', category='c')))
        self.assertTrue(f.filter_change(
            Change(project='p', repository='r', branch='b', category='c', codebase='cb')))

    def test_filter_change_combination_filter_fn(self):
        f = ChangeFilter(project='p', repository='r', branch='b', category='c',
                       filter_fn=lambda c: c.ff)
        self.assertFalse(f.filter_change(
            Change(project='x', repository='x', branch='x', category='x', ff=False)))
        self.assertFalse(f.filter_change(
            Change(project='p', repository='r', branch='b', category='c', ff=False)))
        self.assertFalse(f.filter_change(
            Change(project='x', repository='x', branch='x', category='x', ff=True)))
        self.assertTrue(f.filter_change(
            Change(project='p', repository='r', branch='b', category='c', ff=True)))

    def test_filter_props(self):
        f = ChangeFilter(property_eq={'event.type': 'ref-updated'})
        self.assertTrue(f.filter_change(Change(properties={'event.type': 'ref-updated'})))
        self.assertFalse(f.filter_change(Change(properties={'event.type': 'patch-uploaded'})))
        self.assertFalse(f.filter_change(Change(properties={})))
