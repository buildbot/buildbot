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

from buildbot.util.ssfilter import SourceStampFilter
from buildbot.util.ssfilter import extract_filter_values
from buildbot.util.ssfilter import extract_filter_values_branch
from buildbot.util.ssfilter import extract_filter_values_regex


class TestSourceStampFilter(unittest.TestCase):

    def test_extract_filter_values(self):
        self.assertEqual(extract_filter_values([], 'name'), [])
        self.assertEqual(extract_filter_values(['value'], 'name'), ['value'])
        self.assertEqual(extract_filter_values('value', 'name'), ['value'])

        with self.assertRaises(ValueError):
            extract_filter_values({'value'}, 'name')
        with self.assertRaises(ValueError):
            extract_filter_values(None, 'name')
        with self.assertRaises(ValueError):
            extract_filter_values([{'value'}], 'name')
        with self.assertRaises(ValueError):
            extract_filter_values([None], 'name')

    def test_extract_filter_values_branch(self):
        self.assertEqual(extract_filter_values_branch([], 'name'), [])
        self.assertEqual(extract_filter_values_branch(['value'], 'name'), ['value'])
        self.assertEqual(extract_filter_values_branch('value', 'name'), ['value'])
        self.assertEqual(extract_filter_values_branch([None], 'name'), [None])
        self.assertEqual(extract_filter_values_branch(None, 'name'), [None])

        with self.assertRaises(ValueError):
            extract_filter_values({'value'}, 'name')
        with self.assertRaises(ValueError):
            extract_filter_values([{'value'}], 'name')

    def test_extract_filter_values_regex(self):
        self.assertEqual(extract_filter_values_regex([], 'name'), [])
        self.assertEqual(extract_filter_values_regex(['value'], 'name'), ['value'])
        self.assertEqual(extract_filter_values_regex('value', 'name'), ['value'])
        self.assertEqual(extract_filter_values_regex([re.compile('test')], 'name'),
                         [re.compile('test')])
        self.assertEqual(extract_filter_values_regex(re.compile('test'), 'name'),
                         [re.compile('test')])

        with self.assertRaises(ValueError):
            extract_filter_values({'value'}, 'name')
        with self.assertRaises(ValueError):
            extract_filter_values([{'value'}], 'name')

    @parameterized.expand([
        ('match', {'project': 'p', 'codebase': 'c', 'repository': 'r', 'branch': 'b'}, True),
        ('not_project', {'project': '0', 'codebase': 'c', 'repository': 'r', 'branch': 'b'},
         False),
        ('not_codebase', {'project': 'p', 'codebase': '0', 'repository': 'r', 'branch': 'b'},
         False),
        ('not_repository', {'project': 'p', 'codebase': 'c', 'repository': '0', 'branch': 'b'},
         False),
        ('not_branch', {'project': 'p', 'codebase': 'c', 'repository': 'r', 'branch': '0'},
         False),
        ('none_branch', {'project': 'p', 'codebase': 'c', 'repository': 'r', 'branch': None},
         False),
    ])
    def test_filter_is_matched_eq_or_re(self, name, ss, expected):
        filter = SourceStampFilter(project_eq='p', codebase_eq='c', repository_eq='r',
                                   branch_eq='b')
        self.assertEqual(filter.is_matched(ss), expected)

        filter = SourceStampFilter(project_re='^p$', codebase_re='^c$', repository_re='^r$',
                                   branch_re='^b$')
        self.assertEqual(filter.is_matched(ss), expected)

        filter = SourceStampFilter(project_re=re.compile('^p$'),
                                   codebase_re=re.compile('^c$'),
                                   repository_re=re.compile('^r$'),
                                   branch_re=re.compile('^b$'))
        self.assertEqual(filter.is_matched(ss), expected)

    @parameterized.expand([
        ('match', {'project': 'p', 'codebase': 'c', 'repository': 'r', 'branch': 'b'}, True),
        ('not_project', {'project': 'p0', 'codebase': 'c', 'repository': 'r', 'branch': 'b'},
         False),
        ('not_codebase', {'project': 'p', 'codebase': 'c0', 'repository': 'r', 'branch': 'b'},
         False),
        ('not_repository', {'project': 'p', 'codebase': 'c', 'repository': 'r0', 'branch': 'b'},
         False),
        ('not_branch', {'project': 'p', 'codebase': 'c', 'repository': 'r', 'branch': 'b0'},
         False),
        ('none_branch', {'project': 'p', 'codebase': 'c', 'repository': 'r', 'branch': None},
         True)
    ])
    def test_filter_is_matched_not_eq_or_re(self, name, ss, expected):
        filter = SourceStampFilter(project_not_eq='p0', codebase_not_eq='c0',
                                   repository_not_eq='r0', branch_not_eq='b0')
        self.assertEqual(filter.is_matched(ss), expected)

        filter = SourceStampFilter(project_not_re='^p0$', codebase_not_re='^c0$',
                                   repository_not_re='^r0$',
                                   branch_not_re='^b0$')
        self.assertEqual(filter.is_matched(ss), expected)

        filter = SourceStampFilter(project_not_re=re.compile('^p0$'),
                                   codebase_not_re=re.compile('^c0$'),
                                   repository_not_re=re.compile('^r0$'),
                                   branch_not_re=re.compile('^b0$'))
        self.assertEqual(filter.is_matched(ss), expected)

    def test_filter_repr(self):
        filter = SourceStampFilter(project_eq='p', codebase_eq='c',
                                   repository_eq='r', branch_eq='b',
                                   project_re='^p$', codebase_re='^c$',
                                   repository_re='^r$', branch_re='^b$',
                                   project_not_eq='p0', codebase_not_eq='c0',
                                   repository_not_eq='r0', branch_not_eq='b0',
                                   project_not_re='^p0$', codebase_not_re='^c0$',
                                   repository_not_re='^r0$', branch_not_re='^b0$')
        self.assertEqual(repr(filter),
                         "<SourceStampFilter on project in ['p'] and project not in ['p0'] " +
                         "and project matches [re.compile('^p$')] " +
                         "and project does not match [re.compile('^p0$')] " +
                         "and codebase in ['c'] and codebase not in ['c0'] " +
                         "and codebase matches [re.compile('^c$')] " +
                         "and codebase does not match [re.compile('^c0$')] " +
                         "and repository in ['r'] and repository not in ['r0'] " +
                         "and repository matches [re.compile('^r$')] " +
                         "and repository does not match [re.compile('^r0$')] " +
                         "and branch in ['b'] and branch not in ['b0'] " +
                         "and branch matches [re.compile('^b$')] " +
                         "and branch does not match [re.compile('^b0$')]>")
