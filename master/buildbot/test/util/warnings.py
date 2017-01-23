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

# Utility functions for catching Python warnings.
# Twisted's TestCase already gathers produced warnings
# (see t.t.u.T.flushWarnings()), however Twisted's implementation doesn't
# allow fine-grained control over caught warnings.
# This implementation uses context wrapper style to specify interesting
# block of code to catch warnings, which allows to easily specify which
# exactly statements should generate warnings and which shouldn't.
# Also this implementation allows nested checks.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import re
import warnings


@contextlib.contextmanager
def _recordWarnings(category, output):
    assert isinstance(output, list)

    unrelated_warns = []
    with warnings.catch_warnings(record=True) as all_warns:
        # Cause all warnings of the provided category to always be
        # triggered.
        warnings.simplefilter("always", category)

        yield

        # Filter warnings.
        for w in all_warns:
            if isinstance(w.message, category):
                output.append(w)
            else:
                unrelated_warns.append(w)

    # Re-raise unrelated warnings.
    for w in unrelated_warns:
        warnings.warn_explicit(w.message, w.category, w.filename, w.lineno)


@contextlib.contextmanager
def assertProducesWarnings(filter_category, num_warnings=None,
                           messages_patterns=None, message_pattern=None):
    if messages_patterns is not None:
        assert message_pattern is None
        assert num_warnings is None
        num_warnings = len(messages_patterns)
    else:
        assert num_warnings is not None or message_pattern is not None

    warns = []
    with _recordWarnings(filter_category, warns):
        yield

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
            # TODO: Maybe don't use regexp, but use simple substring check?
            assert re.search(pattern, str(w.message)), \
                "Warning pattern doesn't match. Expected pattern:\n" \
                "{pattern}\n" \
                "Received message:\n" \
                "{message}\n" \
                "All gathered warnings:\n" \
                "{warns}".format(pattern=pattern, message=w.message,
                                 warns="\n".join(map(str, warns)))


@contextlib.contextmanager
def assertProducesWarning(filter_category, message_pattern=None):
    with assertProducesWarnings(filter_category, num_warnings=1,
                                message_pattern=message_pattern):
        yield


@contextlib.contextmanager
def assertNotProducesWarnings(filter_category):
    with assertProducesWarnings(filter_category, 0):
        yield


@contextlib.contextmanager
def ignoreWarning(category):
    with _recordWarnings(category, []):
        yield
