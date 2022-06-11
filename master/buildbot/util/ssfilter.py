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

from buildbot.util import ComparableMixin
from buildbot.util import NotABranch


def is_re_pattern(obj):
    # re.Pattern only exists in Python 3.7
    return hasattr(obj, 'search') and hasattr(obj, 'match')


def extract_filter_values(values, filter_name):
    if not isinstance(values, (list, str)):
        raise ValueError(f"Values of filter {filter_name} must be list of strings or a string")
    if isinstance(values, str):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, str):
                raise ValueError(f"Value of filter {filter_name} must be string")
    return values


def extract_filter_values_branch(values, filter_name):
    if not isinstance(values, (list, str, type(None))):
        raise ValueError(f"Values of filter {filter_name} must be list of strings, "
                         "a string or None")
    if isinstance(values, (str, type(None))):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, (str, type(None))):
                raise ValueError(f"Value of filter {filter_name} must be string or None")
    return values


def extract_filter_values_regex(values, filter_name):
    if not isinstance(values, (list, str)) and not is_re_pattern(values):
        raise ValueError(f"Values of filter {filter_name} must be list of strings, "
                         "a string or regex")
    if isinstance(values, str) or is_re_pattern(values):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, str) and not is_re_pattern(value):
                raise ValueError(f"Value of filter {filter_name} must be string or regex")
    return values


class _FilterExactMatch:
    def __init__(self, values):
        self.values = values

    def is_matched(self, value):
        return value in self.values

    def describe(self, prop):
        return f'{prop} in {self.values}'


class _FilterExactMatchInverse:
    def __init__(self, values):
        self.values = values

    def is_matched(self, value):
        return value not in self.values

    def describe(self, prop):
        return f'{prop} not in {self.values}'


class _FilterRegex:
    def __init__(self, regexes):
        self.regexes = [self._compile(regex) for regex in regexes]

    def _compile(self, regex):
        if is_re_pattern(regex):
            return regex
        return re.compile(regex)

    def is_matched(self, value):
        if value is None:
            return False
        for regex in self.regexes:
            if regex.match(value) is not None:
                return True
        return False

    def describe(self, prop):
        return f'{prop} matches {self.regexes}'


class _FilterRegexInverse:
    def __init__(self, regexes):
        self.regexes = [self._compile(regex) for regex in regexes]

    def _compile(self, regex):
        if is_re_pattern(regex):
            return regex
        return re.compile(regex)

    def is_matched(self, value):
        if value is None:
            return True
        for regex in self.regexes:
            if regex.match(value) is not None:
                return False
        return True

    def describe(self, prop):
        return f'{prop} does not match {self.regexes}'


class SourceStampFilter(ComparableMixin):

    compare_attrs = (
        'filter_fn',
        'project_filters',
        'codebase_filters',
        'repository_filters',
        'branch_filters'
    )

    def __init__(self,
                 # gets a SourceStamp dictionary, returns boolean
                 filter_fn=None,

                 project_eq=None, project_not_eq=None, project_re=None, project_not_re=None,
                 repository_eq=None, repository_not_eq=None,
                 repository_re=None, repository_not_re=None,
                 branch_eq=NotABranch, branch_not_eq=NotABranch, branch_re=None, branch_not_re=None,
                 codebase_eq=None, codebase_not_eq=None, codebase_re=None, codebase_not_re=None):

        self.filter_fn = filter_fn
        self.project_filters = self.create_filters(project_eq, project_not_eq,
                                                   project_re, project_not_re, 'project')
        self.codebase_filters = self.create_filters(codebase_eq, codebase_not_eq,
                                                    codebase_re, codebase_not_re, 'codebase')
        self.repository_filters = self.create_filters(repository_eq, repository_not_eq,
                                                      repository_re, repository_not_re,
                                                      'repository')
        self.branch_filters = self.create_branch_filters(branch_eq, branch_not_eq,
                                                         branch_re, branch_not_re, 'branch')

    def create_branch_filters(self, eq, not_eq, regex, not_regex, filter_name):
        filters = []
        if eq is not NotABranch:
            values = extract_filter_values_branch(eq, filter_name + '_eq')
            filters.append(_FilterExactMatch(values))

        if not_eq is not NotABranch:
            values = extract_filter_values_branch(not_eq, filter_name + '_not_eq')
            filters.append(_FilterExactMatchInverse(values))

        if regex is not None:
            values = extract_filter_values_regex(regex, filter_name + '_re')
            filters.append(_FilterRegex(values))

        if not_regex is not None:
            values = extract_filter_values_regex(not_regex, filter_name + '_re')
            filters.append(_FilterRegexInverse(values))

        return filters

    def create_filters(self, eq, not_eq, regex, not_regex, filter_name):
        filters = []
        if eq is not None:
            values = extract_filter_values(eq, filter_name + '_eq')
            filters.append(_FilterExactMatch(values))

        if not_eq is not None:
            values = extract_filter_values(not_eq, filter_name + '_not_eq')
            filters.append(_FilterExactMatchInverse(values))

        if regex is not None:
            values = extract_filter_values_regex(regex, filter_name + '_re')
            filters.append(_FilterRegex(values))

        if not_regex is not None:
            values = extract_filter_values_regex(not_regex, filter_name + '_re')
            filters.append(_FilterRegexInverse(values))

        return filters

    def do_prop_match(self, ss, prop, filters):
        value = ss.get(prop, '')
        for filter in filters:
            if not filter.is_matched(value):
                return False
        return True

    def is_matched(self, ss):
        if self.filter_fn is not None and not self.filter_fn(ss):
            return False
        if self.project_filters and not self.do_prop_match(ss, 'project', self.project_filters):
            return False
        if self.codebase_filters and not self.do_prop_match(ss, 'codebase', self.codebase_filters):
            return False
        if self.repository_filters and \
                not self.do_prop_match(ss, 'repository', self.repository_filters):
            return False
        if self.branch_filters and not self.do_prop_match(ss, 'branch', self.branch_filters):
            return False
        return True

    def is_matched_codebase(self, codebase):
        for filter in self.codebase_filters:
            if not filter.is_matched(codebase):
                return False
        return True

    def _repr_filters(self, filters, prop):
        return [filter.describe(prop) for filter in filters]

    def __repr__(self):
        filters = []
        if self.filter_fn is not None:
            filters.append(f'{self.filter_fn.__name__}()')
        filters += self._repr_filters(self.project_filters, 'project')
        filters += self._repr_filters(self.codebase_filters, 'codebase')
        filters += self._repr_filters(self.repository_filters, 'repository')
        filters += self._repr_filters(self.branch_filters, 'branch')

        return f"<{self.__class__.__name__} on {' and '.join(filters)}>"
