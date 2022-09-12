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
    if not isinstance(values, (list, str, re.Pattern)):
        raise ValueError(f"Values of filter {filter_name} must be list of strings, "
                         "a string or regex")
    if isinstance(values, (str, re.Pattern)):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, (str, re.Pattern)):
                raise ValueError(f"Value of filter {filter_name} must be string or regex")
    return values


def extract_filter_values_dict(values, filter_name):
    if not isinstance(values, dict):
        raise ValueError(f"Value of filter {filter_name} must be dict")
    return {k: extract_filter_values(v, filter_name) for k, v in values.items()}


def extract_filter_values_dict_regex(values, filter_name):
    if not isinstance(values, dict):
        raise ValueError(f"Value of filter {filter_name} must be dict")
    return {k: extract_filter_values_regex(v, filter_name) for k, v in values.items()}


class _FilterExactMatch(ComparableMixin):
    compare_attrs = ('prop', 'values')

    def __init__(self, prop, values):
        self.prop = prop
        self.values = values

    def is_matched(self, value):
        return value in self.values

    def describe(self):
        return f'{self.prop} in {self.values}'


class _FilterExactMatchInverse(ComparableMixin):
    compare_attrs = ('prop', 'values')

    def __init__(self, prop, values):
        self.prop = prop
        self.values = values

    def is_matched(self, value):
        return value not in self.values

    def describe(self):
        return f'{self.prop} not in {self.values}'


class _FilterRegex(ComparableMixin):
    compare_attrs = ('prop', 'regexes')

    def __init__(self, prop, regexes):
        self.prop = prop
        self.regexes = [self._compile(regex) for regex in regexes]

    def _compile(self, regex):
        if isinstance(regex, re.Pattern):
            return regex
        return re.compile(regex)

    def is_matched(self, value):
        if value is None:
            return False
        for regex in self.regexes:
            if regex.match(value) is not None:
                return True
        return False

    def describe(self):
        return f'{self.prop} matches {self.regexes}'


class _FilterRegexInverse(ComparableMixin):
    compare_attrs = ('prop', 'regexes')

    def __init__(self, prop, regexes):
        self.prop = prop
        self.regexes = [self._compile(regex) for regex in regexes]

    def _compile(self, regex):
        if isinstance(regex, re.Pattern):
            return regex
        return re.compile(regex)

    def is_matched(self, value):
        if value is None:
            return True
        for regex in self.regexes:
            if regex.match(value) is not None:
                return False
        return True

    def describe(self):
        return f'{self.prop} does not match {self.regexes}'


def _create_branch_filters(eq, not_eq, regex, not_regex, prop):
    filters = []
    if eq is not NotABranch:
        values = extract_filter_values_branch(eq, prop + '_eq')
        filters.append(_FilterExactMatch(prop, values))

    if not_eq is not NotABranch:
        values = extract_filter_values_branch(not_eq, prop + '_not_eq')
        filters.append(_FilterExactMatchInverse(prop, values))

    if regex is not None:
        values = extract_filter_values_regex(regex, prop + '_re')
        filters.append(_FilterRegex(prop, values))

    if not_regex is not None:
        values = extract_filter_values_regex(not_regex, prop + '_not_re')
        filters.append(_FilterRegexInverse(prop, values))

    return filters


def _create_filters(eq, not_eq, regex, not_regex, prop):
    filters = []
    if eq is not None:
        values = extract_filter_values(eq, prop + '_eq')
        filters.append(_FilterExactMatch(prop, values))

    if not_eq is not None:
        values = extract_filter_values(not_eq, prop + '_not_eq')
        filters.append(_FilterExactMatchInverse(prop, values))

    if regex is not None:
        values = extract_filter_values_regex(regex, prop + '_re')
        filters.append(_FilterRegex(prop, values))

    if not_regex is not None:
        values = extract_filter_values_regex(not_regex, prop + '_not_re')
        filters.append(_FilterRegexInverse(prop, values))

    return filters


def _create_property_filters(eq, not_eq, regex, not_regex, arg_prefix):
    filters = []
    if eq is not None:
        values_dict = extract_filter_values_dict(eq, arg_prefix + '_eq')
        filters += [_FilterExactMatch(prop, values) for prop, values in values_dict.items()]

    if not_eq is not None:
        values_dict = extract_filter_values_dict(not_eq, arg_prefix + '_not_eq')
        filters += [_FilterExactMatchInverse(prop, values) for prop, values in values_dict.items()]

    if regex is not None:
        values_dict = extract_filter_values_dict_regex(regex, arg_prefix + '_re')
        filters += [_FilterRegex(prop, values) for prop, values in values_dict.items()]

    if not_regex is not None:
        values_dict = extract_filter_values_dict_regex(not_regex, arg_prefix + '_not_re')
        filters += [_FilterRegexInverse(prop, values) for prop, values in values_dict.items()]

    return filters


class SourceStampFilter(ComparableMixin):

    compare_attrs = (
        'filter_fn',
        'filters',
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
        self.filters = _create_filters(
            project_eq,
            project_not_eq,
            project_re,
            project_not_re,
            'project',
        )
        self.filters += _create_filters(
            codebase_eq,
            codebase_not_eq,
            codebase_re,
            codebase_not_re,
            'codebase',
        )
        self.filters += _create_filters(
            repository_eq,
            repository_not_eq,
            repository_re,
            repository_not_re,
            'repository',
        )
        self.filters += _create_branch_filters(
            branch_eq,
            branch_not_eq,
            branch_re,
            branch_not_re,
            'branch',
        )

    def is_matched(self, ss):
        if self.filter_fn is not None and not self.filter_fn(ss):
            return False
        for filter in self.filters:
            value = ss.get(filter.prop, '')
            if not filter.is_matched(value):
                return False
        return True

    def __repr__(self):
        filters = []
        if self.filter_fn is not None:
            filters.append(f'{self.filter_fn.__name__}()')
        filters += [filter.describe() for filter in self.filters]
        return f"<{self.__class__.__name__} on {' and '.join(filters)}>"
