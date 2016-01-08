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

import contextlib
import re
import warnings


@contextlib.contextmanager
def assertProducesWarnings(filter_category, num_warnings=None,
                           messages_patterns=None, message_pattern=None):
    if messages_patterns is not None:
        assert message_pattern is None
        assert num_warnings is None
        num_warnings = len(messages_patterns)
    else:
        assert num_warnings is not None or message_pattern is not None

    with warnings.catch_warnings(record=True) as warns:
        # Cause all warnings of the provided category to always be
        # triggered.
        warnings.simplefilter("always", filter_category)

        yield

        # Filter warnings.
        warns = [w for w in warns if isinstance(w.message, filter_category)]

        if num_warnings is not None:
            assert len(warns) == num_warnings, \
                "Number of of occurred warnings is not correct. " \
                "Expected {num} warnings, received {num_received}:\n" \
                "{warns}".format(
                    num=num_warnings,
                    num_received=len(warns),
                    warns="\n".join(map(str, warns)))

        num_warnings = len(warns)
        if messages_patterns is None and message_pattern is not None:
            messages_patterns = [message_pattern] * num_warnings

        if messages_patterns is not None:
            for w, pattern in zip(warns, messages_patterns):
                assert re.search(pattern, str(w.message)), \
                    "Warning pattern doesn't match. Expected pattern:\n" \
                    "{pattern}\n" \
                    "Received message:\n" \
                    "{message}\n" \
                    "All gathered warnings:\n" \
                    "{warns}".format(pattern=pattern, message=w.message,
                                     warns="\n".join(map(str, warns)))


@contextlib.contextmanager
def assertProducesWarning(filter_category, messages_patterns=None,
                          message_pattern=None):
    with assertProducesWarnings(filter_category, num_warnings=1,
                                messages_patterns=messages_patterns,
                                message_pattern=message_pattern):
        yield


@contextlib.contextmanager
def assertNotProducesWarnings(filter_category):
    with assertProducesWarnings(filter_category, 0):
        yield
