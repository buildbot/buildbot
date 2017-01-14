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

import re

from twisted.trial import unittest

from buildbot.changes import filter
from buildbot.test.fake.change import Change


class ChangeFilter(unittest.TestCase):

    def setUp(self):
        self.results = []  # (got, expected, msg)
        self.filt = None

    def tearDown(self):
        if self.results:
            raise RuntimeError("test forgot to call check()")

    def setfilter(self, **kwargs):
        self.filt = filter.ChangeFilter(**kwargs)

    def yes(self, change, msg):
        self.results.append((self.filt.filter_change(change), True, msg))

    def no(self, change, msg):
        self.results.append((self.filt.filter_change(change), False, msg))

    def check(self):
        errs = []
        for r in self.results:
            if (r[0] or r[1]) and not (r[0] and r[1]):
                errs.append(r[2])
        self.results = []
        if errs:
            self.fail("; ".join(errs))

    def test_filter_change_filter_fn(self):
        self.setfilter(filter_fn=lambda ch: ch.x > 3)
        self.no(Change(x=2), "filter_fn returns False")
        self.yes(Change(x=4), "filter_fn returns True")
        self.check()

    def test_filter_change_filt_str(self):
        self.setfilter(project="myproj")
        self.no(Change(project="yourproj"),
                "non-matching PROJECT returns False")
        self.yes(Change(project="myproj"), "matching PROJECT returns True")
        self.check()

    def test_filter_change_filt_list(self):
        self.setfilter(repository=["vc://a", "vc://b"])
        self.yes(Change(repository="vc://a"),
                 "matching REPOSITORY vc://a returns True")
        self.yes(Change(repository="vc://b"),
                 "matching REPOSITORY vc://b returns True")
        self.no(Change(repository="vc://c"),
                "non-matching REPOSITORY returns False")
        self.no(Change(repository=None), "None for REPOSITORY returns False")
        self.check()

    def test_filter_change_filt_list_None(self):
        self.setfilter(branch=["mybr", None])
        self.yes(Change(branch="mybr"), "matching BRANCH mybr returns True")
        self.yes(Change(branch=None), "matching BRANCH None returns True")
        self.no(Change(branch="misc"), "non-matching BRANCH returns False")
        self.check()

    def test_filter_change_filt_re(self):
        self.setfilter(category_re="^a.*")
        self.yes(Change(category="albert"), "matching CATEGORY returns True")
        self.no(
            Change(category="boris"), "non-matching CATEGORY returns False")
        self.check()

    def test_filter_change_branch_re(self):  # regression - see #927
        self.setfilter(branch_re="^t.*")
        self.yes(Change(branch="trunk"), "matching BRANCH returns True")
        self.no(Change(branch="development"),
                "non-matching BRANCH returns False")
        self.no(Change(branch=None), "branch=None returns False")
        self.check()

    def test_filter_change_filt_re_compiled(self):
        self.setfilter(category_re=re.compile("^b.*", re.I))
        self.no(Change(category="albert"),
                "non-matching CATEGORY returns False")
        self.yes(Change(category="boris"), "matching CATEGORY returns True")
        self.yes(
            Change(category="Bruce"), "matching CATEGORY returns True, using re.I")
        self.check()

    def test_filter_change_combination(self):
        self.setfilter(project='p', repository='r', branch='b', category='c',
                       codebase='cb')
        self.no(Change(project='x', repository='x', branch='x', category='x'),
                "none match -> False")
        self.no(Change(project='p', repository='r', branch='b', category='x'),
                "three match -> False")
        self.no(Change(project='p', repository='r', branch='b', category='c',
                       codebase='x'), "four match -> False")
        self.yes(Change(project='p', repository='r', branch='b', category='c',
                        codebase='cb'), "all match -> True")
        self.check()

    def test_filter_change_combination_filter_fn(self):
        self.setfilter(project='p', repository='r', branch='b', category='c',
                       filter_fn=lambda c: c.ff)
        self.no(Change(project='x', repository='x', branch='x', category='x', ff=False),
                "none match and fn returns False -> False")
        self.no(Change(project='p', repository='r', branch='b', category='c', ff=False),
                "all match and fn returns False -> False")
        self.no(Change(project='x', repository='x', branch='x', category='x', ff=True),
                "none match and fn returns True -> False")
        self.yes(Change(project='p', repository='r', branch='b', category='c', ff=True),
                 "all match and fn returns True -> False")
        self.check()

    def test_filter_props(self):
        self.setfilter()
        self.filt.checks.update(
            self.filt.createChecks(
                ("ref-updated", None, None, "prop:event.type"),
            ))
        self.yes(
            Change(properties={'event.type': 'ref-updated'}), "matching property")
        self.no(
            Change(properties={'event.type': 'patch-uploaded'}), "non matching property")
        self.no(Change(properties={}), "no property")
        self.check()
