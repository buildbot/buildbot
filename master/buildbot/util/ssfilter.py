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

import re
from typing import TYPE_CHECKING
from typing import Callable
from typing import ClassVar

from buildbot.util import ComparableMixin
from buildbot.util import NotABranch
from buildbot.util import _NotABranch

if TYPE_CHECKING:
    from collections.abc import Sequence


def extract_filter_values(values: list[str] | str, filter_name: str) -> list[str]:
    if not isinstance(values, (list, str)):
        raise ValueError(f"Values of filter {filter_name} must be list of strings or a string")
    if isinstance(values, str):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, str):
                raise ValueError(f"Value of filter {filter_name} must be string")
    return values


def extract_filter_values_branch(
    values: list[str | None] | str | None,
    filter_name: str,
) -> list[str | None]:
    if not isinstance(values, (list, str, type(None))):
        raise ValueError(
            f"Values of filter {filter_name} must be list of strings, a string or None"
        )
    if isinstance(values, (str, type(None))):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, (str, type(None))):
                raise ValueError(f"Value of filter {filter_name} must be string or None")
    return values


def extract_filter_values_regex(
    values: list[str | re.Pattern[str]] | str | re.Pattern[str],
    filter_name: str,
) -> list[str | re.Pattern[str]]:
    if not isinstance(values, (list, str, re.Pattern)):
        raise ValueError(
            f"Values of filter {filter_name} must be list of strings, a string or regex"
        )
    if isinstance(values, (str, re.Pattern)):
        values = [values]
    else:
        for value in values:
            if not isinstance(value, (str, re.Pattern)):
                raise ValueError(f"Value of filter {filter_name} must be string or regex")
    return values


def extract_filter_values_dict(
    values: dict[str, list[str] | str],
    filter_name: str,
) -> dict[str, list[str]]:
    if not isinstance(values, dict):
        raise ValueError(f"Value of filter {filter_name} must be dict")
    return {k: extract_filter_values(v, filter_name) for k, v in values.items()}


def extract_filter_values_dict_regex(
    values: dict[str, list[str | re.Pattern[str]] | str | re.Pattern[str]],
    filter_name: str,
) -> dict[str, list[str | re.Pattern[str]]]:
    if not isinstance(values, dict):
        raise ValueError(f"Value of filter {filter_name} must be dict")
    return {k: extract_filter_values_regex(v, filter_name) for k, v in values.items()}


class _FilterMatchBase:
    def __init__(self, prop: str) -> None:
        self.prop = prop

    def is_matched(self, value: str | None) -> bool:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class _FilterExactMatch(_FilterMatchBase, ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = ('prop', 'values')

    def __init__(self, prop: str, values: Sequence[str | None]) -> None:
        super().__init__(prop=prop)
        self.values = values

    def is_matched(self, value: str | None) -> bool:
        return value in self.values

    def describe(self) -> str:
        return f'{self.prop} in {self.values}'


class _FilterExactMatchInverse(_FilterMatchBase, ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = ('prop', 'values')

    def __init__(self, prop: str, values: Sequence[str | None]) -> None:
        super().__init__(prop=prop)
        self.values = values

    def is_matched(self, value: str | None) -> bool:
        return value not in self.values

    def describe(self) -> str:
        return f'{self.prop} not in {self.values}'


class _FilterRegex(_FilterMatchBase, ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = ('prop', 'regexes')

    def __init__(self, prop: str, regexes: Sequence[str | re.Pattern[str]]) -> None:
        super().__init__(prop=prop)
        self.regexes = [self._compile(regex) for regex in regexes]

    def _compile(self, regex: str | re.Pattern[str]) -> re.Pattern[str]:
        if isinstance(regex, re.Pattern):
            return regex
        return re.compile(regex)

    def is_matched(self, value: str | None) -> bool:
        if value is None:
            return False
        for regex in self.regexes:
            if regex.match(value) is not None:
                return True
        return False

    def describe(self) -> str:
        return f'{self.prop} matches {self.regexes}'


class _FilterRegexInverse(_FilterMatchBase, ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = ('prop', 'regexes')

    def __init__(self, prop: str, regexes: Sequence[str | re.Pattern[str]]) -> None:
        super().__init__(prop=prop)
        self.regexes = [self._compile(regex) for regex in regexes]

    def _compile(self, regex: str | re.Pattern[str]) -> re.Pattern[str]:
        if isinstance(regex, re.Pattern):
            return regex
        return re.compile(regex)

    def is_matched(self, value: str | None) -> bool:
        if value is None:
            return True
        for regex in self.regexes:
            if regex.match(value) is not None:
                return False
        return True

    def describe(self) -> str:
        return f'{self.prop} does not match {self.regexes}'


def _create_branch_filters(
    eq: list[str | None] | str | None | _NotABranch,
    not_eq: list[str | None] | str | None | _NotABranch,
    regex: list[str | re.Pattern[str]] | str | re.Pattern[str] | None,
    not_regex: list[str | re.Pattern[str]] | str | re.Pattern[str] | None,
    prop: str,
) -> list[_FilterMatchBase]:
    filters: list[_FilterMatchBase] = []
    if eq is not NotABranch:
        assert not isinstance(eq, _NotABranch)
        filters.append(_FilterExactMatch(prop, extract_filter_values_branch(eq, prop + '_eq')))

    if not_eq is not NotABranch:
        assert not isinstance(not_eq, _NotABranch)
        filters.append(
            _FilterExactMatchInverse(prop, extract_filter_values_branch(not_eq, prop + '_not_eq'))
        )

    if regex is not None:
        filters.append(_FilterRegex(prop, extract_filter_values_regex(regex, prop + '_re')))

    if not_regex is not None:
        filters.append(
            _FilterRegexInverse(prop, extract_filter_values_regex(not_regex, prop + '_not_re'))
        )

    return filters


def _create_filters(
    eq: str | list[str] | None,
    not_eq: str | list[str] | None,
    regex: list[str | re.Pattern[str]] | str | re.Pattern[str] | None,
    not_regex: list[str | re.Pattern[str]] | str | re.Pattern[str] | None,
    prop: str,
) -> list[_FilterMatchBase]:
    filters: list[_FilterMatchBase] = []
    if eq is not None:
        filters.append(_FilterExactMatch(prop, extract_filter_values(eq, prop + '_eq')))

    if not_eq is not None:
        filters.append(
            _FilterExactMatchInverse(prop, extract_filter_values(not_eq, prop + '_not_eq'))
        )

    if regex is not None:
        filters.append(_FilterRegex(prop, extract_filter_values_regex(regex, prop + '_re')))

    if not_regex is not None:
        filters.append(
            _FilterRegexInverse(prop, extract_filter_values_regex(not_regex, prop + '_not_re'))
        )

    return filters


def _create_property_filters(
    eq: dict[str, list[str] | str] | None,
    not_eq: dict[str, list[str] | str] | None,
    regex: dict[str, list[str | re.Pattern[str]] | str | re.Pattern[str]] | None,
    not_regex: dict[str, list[str | re.Pattern[str]] | str | re.Pattern[str]] | None,
    arg_prefix: str,
) -> list[_FilterMatchBase]:
    filters: list[_FilterMatchBase] = []
    if eq is not None:
        filters += [
            _FilterExactMatch(prop, values)
            for prop, values in extract_filter_values_dict(eq, arg_prefix + '_eq').items()
        ]

    if not_eq is not None:
        filters += [
            _FilterExactMatchInverse(prop, values)
            for prop, values in extract_filter_values_dict(not_eq, arg_prefix + '_not_eq').items()
        ]

    if regex is not None:
        filters += [
            _FilterRegex(prop, values)
            for prop, values in extract_filter_values_dict_regex(regex, arg_prefix + '_re').items()
        ]

    if not_regex is not None:
        filters += [
            _FilterRegexInverse(prop, values)
            for prop, values in extract_filter_values_dict_regex(
                not_regex, arg_prefix + '_not_re'
            ).items()
        ]

    return filters


class SourceStampFilter(ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = (
        'filter_fn',
        'filters',
    )

    def __init__(
        self,
        # gets a SourceStamp dictionary, returns boolean
        filter_fn: Callable[[dict[str, str | None]], bool] | None = None,
        project_eq: str | None = None,
        project_not_eq: str | None = None,
        project_re: str | re.Pattern[str] | None = None,
        project_not_re: str | re.Pattern[str] | None = None,
        repository_eq: str | list[str] | None = None,
        repository_not_eq: str | None = None,
        repository_re: str | re.Pattern[str] | None = None,
        repository_not_re: str | re.Pattern[str] | None = None,
        branch_eq: list[str | None] | str | None | _NotABranch = NotABranch,
        branch_not_eq: str | _NotABranch = NotABranch,
        branch_re: str | re.Pattern[str] | None = None,
        branch_not_re: str | re.Pattern[str] | None = None,
        codebase_eq: str | list[str] | None = None,
        codebase_not_eq: str | None = None,
        codebase_re: str | re.Pattern[str] | None = None,
        codebase_not_re: str | re.Pattern[str] | None = None,
    ) -> None:
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

    def is_matched(self, ss: dict[str, str | None]) -> bool:
        if self.filter_fn is not None and not self.filter_fn(ss):
            return False
        for filter in self.filters:
            value = ss.get(filter.prop, '')
            if not filter.is_matched(value):
                return False
        return True

    def __repr__(self) -> str:
        filters: list[str] = []
        if self.filter_fn is not None:
            filters.append(f'{self.filter_fn.__name__}()')
        filters += [filter.describe() for filter in self.filters]
        return f"<{self.__class__.__name__} on {' and '.join(filters)}>"
