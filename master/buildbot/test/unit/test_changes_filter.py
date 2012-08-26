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

from buildbot.changes import filter
from buildbot.test.fake.state import State

class Change(State):
    project = ''
    repository = ''
    branch = ''
    category = ''
    tags = None

class ChangeFilter(unittest.TestCase):

    def setUp(self):
        self.results = [] # (got, expected, msg)
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
        self.setfilter(filter_fn = lambda ch : ch.x > 3)
        self.no(Change(x=2), "filter_fn returns False")
        self.yes(Change(x=4), "filter_fn returns True")
        self.check()

    def test_filter_change_filt_str(self):
        self.setfilter(project = "myproj")
        self.no(Change(project="yourproj"), "non-matching PROJECT returns False")
        self.yes(Change(project="myproj"), "matching PROJECT returns True")
        self.check()

    def test_filter_change_filt_list(self):
        self.setfilter(repository = ["vc://a", "vc://b"])
        self.yes(Change(repository="vc://a"), "matching REPOSITORY vc://a returns True")
        self.yes(Change(repository="vc://b"), "matching REPOSITORY vc://b returns True")
        self.no(Change(repository="vc://c"), "non-matching REPOSITORY returns False")
        self.no(Change(repository=None), "None for REPOSITORY returns False")
        self.check()

    def test_filter_change_filt_list_None(self):
        self.setfilter(branch = ["mybr", None])
        self.yes(Change(branch="mybr"), "matching BRANCH mybr returns True")
        self.yes(Change(branch=None), "matching BRANCH None returns True")
        self.no(Change(branch="misc"), "non-matching BRANCH returns False")
        self.check()

    def test_filter_change_filt_re(self):
        self.setfilter(category_re = "^a.*")
        self.yes(Change(category="albert"), "matching CATEGORY returns True")
        self.no(Change(category="boris"), "non-matching CATEGORY returns False")
        self.no(Change(category=None), "None for CATEGORY returns False")
        self.check()

    def test_filter_change_branch_re(self): # regression - see #927
        self.setfilter(branch_re = "^t.*")
        self.yes(Change(branch="trunk"), "matching BRANCH returns True")
        self.no(Change(branch="development"), "non-matching BRANCH returns False")
        self.no(Change(branch=None), "branch=None returns False")
        self.check()

    def test_filter_change_filt_re_compiled(self):
        self.setfilter(category_re = re.compile("^b.*", re.I))
        self.no(Change(category="albert"), "non-matching CATEGORY returns False")
        self.yes(Change(category="boris"), "matching CATEGORY returns True")
        self.yes(Change(category="Bruce"), "matching CATEGORY returns True, using re.I")
        self.check()

    def test_filter_change_combination(self):
        self.setfilter(project='p', repository='r', branch='b', category='c')
        self.no(Change(project='x', repository='x', branch='x', category='x'),
                "none match -> False")
        self.no(Change(project='p', repository='r', branch='b', category='x'),
                "three match -> False")
        self.yes(Change(project='p', repository='r', branch='b', category='c'),
                "all match -> True")
        self.check()

    def test_filter_change_combination_filter_fn(self):
        self.setfilter(project='p', repository='r', branch='b', category='c',
                       filter_fn = lambda c : c.ff)
        self.no(Change(project='x', repository='x', branch='x', category='x', ff=False),
                "none match and fn returns False -> False")
        self.no(Change(project='p', repository='r', branch='b', category='c', ff=False),
                "all match and fn returns False -> False")
        self.no(Change(project='x', repository='x', branch='x', category='x', ff=True),
                "none match and fn returns True -> False")
        self.yes(Change(project='p', repository='r', branch='b', category='c', ff=True),
                "all match and fn returns True -> False")
        self.check()

    def test_filter_change_tags_fn(self):
        self.setfilter(tags_fn = lambda t : 'match' in t)
        self.no(Change(tags=['tag-a', 'tag-b']), "tags_fn returns False")
        self.yes(Change(tags=['match', 'tag-b']), "tags_fn returns True")
        self.check()

    def test_filter_change_tags_fn_once(self):
        self.setfilter(tags_fn = lambda t : isinstance(t, list) and len(t) > 0)
        self.no(Change(tags={'tag' : 'tag-a'}), "tags_fn returns False")
        self.yes(Change(tags=['tag-a', 'tag-b']), "tags_fn returns True")
        self.check()

    def test_filter_change_filt_str_tags(self):
        self.setfilter(tags = "mytag")
        self.no(Change(tags=["yourtag", "histag", "hertag"]), "non-matching TAGS returns False")
        self.yes(Change(tags=["yourtag", "histag", "hertag", "mytag"]), "matching TAGS returns True")
        self.check()

    def test_filter_change_filt_list_tags(self):
        self.setfilter(tags = ["tag-a", "tag-b"])
        self.yes(Change(tags=["tag-a", "tag-c"]), "matching TAGS tag-a returns True")
        self.yes(Change(tags=["tag-b", "tag-c"]), "matching TAGS tag-b returns True")
        self.no(Change(tags=["tag-c", "tag-d", "tag-e"]), "non-matching TAGS returns False")
        self.no(Change(tags=None), "None for TAGS returns False")
        self.check()

    def test_filter_change_filt_list_None_tags(self):
        self.setfilter(tags = ["mytag", None])
        self.yes(Change(tags=["mytag", "random"]), "matching TAGS mytag returns True")
        self.yes(Change(tags=None), "matching TAGS None returns True")
        self.no(Change(tags=["misc", "random"]), "non-matching TAGS returns False")
        self.check()

    def test_filter_change_filt_re_tags(self):
        self.setfilter(tags_re = "^a.*")
        self.yes(Change(tags=["albert", "boris"]), "matching TAGS returns True")
        self.no(Change(tags=["boris", "development", None]), "non-matching TAGS returns False")
        self.check()

    def test_filter_change_filt_re_compiled_tags(self):
        self.setfilter(tags_re = re.compile("^b.*", re.I))
        self.no(Change(tags=["albert", "development"]), "non-matching TAGS returns False")
        self.yes(Change(tags=["boris", "albert"]), "matching TAGS returns True")
        self.yes(Change(tags=["Bruce", "albert"]), "matching TAGS returns True, using re.I")
        self.check()

    def test_filter_change_filt_list_and_re_tags(self):
        self.setfilter(tags = ["a-tag", "b-tag"], tags_re = "^a.*")
        self.yes(Change(tags=["a-tag"]), "TAGS a-tag matching list and re returns True")
        self.no(Change(tags=["c-tag"]), "TAGS c-tag non-matching both list and re returns False")
        self.no(Change(tags=["b-tag"]), "TAGS b-tag matching list but non-matching re returns False")
        self.no(Change(tags=["albert"]), "TAGS albert matching re but non-matching list returns False")
        self.no(Change(tags=None), "None for TAGS returns False")
        self.check()
    
    def test_filter_change_filt_list_and_fn_tags(self):
        self.setfilter(tags = ["a-tag", "match"], tags_fn = lambda t : 'match' in t or 'fn-match' in t)
        self.yes(Change(tags=["match"]), "TAGS match matching list and fn returns True")
        self.no(Change(tags=["c-tag"]), "TAGS c-tag non-matching both list and fn returns False")
        self.no(Change(tags=["a-tag"]), "TAGS a-tag matching list but non-matching fn returns False")
        self.no(Change(tags=["fn-match"]), "TAGS fn-match matching fn but non-matching list returns False")
        self.no(Change(tags=None), "None for TAGS returns False")
        self.check()
    
    def test_filter_change_filt_re_and_fn_tags(self):
        self.setfilter(tags_re = "^a.*", tags_fn = lambda t : 'a-tag' in t or 'fn-match' in t)
        self.yes(Change(tags=["a-tag"]), "TAGS a-tag matching re and fn returns True")
        self.no(Change(tags=["c-tag"]), "TAGS c-tag non-matching both re and fn returns False")
        self.no(Change(tags=["albert"]), "TAGS albert matching re but non-matching fn returns False")
        self.no(Change(tags=["fn-match"]), "TAGS fn-match matching fn but non-matching re returns False")
        self.no(Change(tags=None), "None for TAGS returns False")
        self.check()
    
    def test_filter_change_filt_list_and_re_and_fn_tags(self):
        self.setfilter(
            tags    = ["a-tag", "alist-tag", "b-tag", "c-tag"],
            tags_re = "^a.*",
            tags_fn = lambda t : 'a-tag' in t or 'afn-tag' in t or 'b-tag' in t or 'fn-match' in t)
        self.yes(Change(tags=["a-tag"]), "TAGS a-tag matching list, re and fn returns True")
        self.no(Change(tags=["d-tag"]), "TAGS d-tag non-matching all 3 list, re and fn returns False")
        self.no(Change(tags=["c-tag"]), "TAGS c-tag matching list but non-matching re and fn returns False")
        self.no(Change(tags=["albert"]), "TAGS albert matching re but non-matching list and fn returns False")
        self.no(Change(tags=["fn-match"]), "TAGS fn-match matching fn but non-matching list and re returns False")

        self.no(Change(tags=["alist-tag"]), "TAGS alist-tag matching list and re but non-matching fn returns False")
        self.no(Change(tags=["b-tag"]), "TAGS b-tag matching list and fn but non-matching re returns False")
        self.no(Change(tags=["afn-tag"]), "TAGS afn-tag matching re and fn but non-matching list returns False")
        self.no(Change(tags=None), "None for TAGS returns False")
        self.check()
    
    def test_filter_change_combination_tags(self):
        self.setfilter(project='p', repository='r', branch='b', category='c', tags=['d'])
        self.no(Change(project='x', repository='x', branch='x', category='x', tags=['x']),
                "none match -> False")
        self.no(Change(project='p', repository='r', branch='b', category='x', tags=['x']),
                "three match -> False")
        self.no(Change(project='p', repository='r', branch='b', category='c', tags=['x']),
                "non-matching tags -> False")
        self.yes(Change(project='p', repository='r', branch='b', category='c', tags=['d']),
                "all match -> True")
        self.check()
