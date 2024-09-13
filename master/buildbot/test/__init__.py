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

import warnings
from unittest import mock

import setuptools  # force import setuptools before any other distutils imports

from buildbot import monkeypatches
from buildbot.test.util.warnings import (  # noqa pylint: disable=wrong-import-position
    assertProducesWarning,
)
from buildbot.test.util.warnings import (  # noqa pylint: disable=wrong-import-position
    assertProducesWarnings,
)
from buildbot.warnings import DeprecatedApiWarning  # noqa pylint: disable=wrong-import-position

[mock]

# apply the same patches the buildmaster does when it starts
monkeypatches.patch_all()

# enable deprecation warnings
warnings.filterwarnings('always', category=DeprecationWarning)

[setuptools]  # force use for pylint

# This is where we load deprecated module-level APIs to ignore warning produced by importing them.
# After the deprecated API has been removed, leave at least one instance of the import in a
# commented state as reference.

# with assertProducesWarnings(DeprecatedApiWarning,
#                             messages_patterns=[
#                                 r" buildbot\.status\.base has been deprecated",
#                             ]):
#     import buildbot.status.base as _  # noqa

# All deprecated modules should be loaded, consider future warnings in tests as errors.
# In order to not pollute the test outputs,
# warnings in tests shall be forcefully tested with assertProducesWarning,
# or shutdown using the warning module
warnings.filterwarnings('error')
# if buildbot_worker is installed in pip install -e mode, then the docker directory will
# match "import docker", and produce a warning.
# We just suppress this warning instead of doing silly workaround.
warnings.filterwarnings(
    'ignore', "Not importing directory.*docker': missing __init__.py", category=ImportWarning
)

# autobahn is not updated for Twisted 22.04 and newer
warnings.filterwarnings(
    "ignore", "twisted.web.resource.NoResource was deprecated in", category=DeprecationWarning
)

# When using Python 3.12, this generates some dependent package
warnings.filterwarnings(
    'ignore',
    r"datetime.datetime.utcnow\(\) is deprecated and scheduled for "
    r"removal in a future version. Use timezone-aware objects to represent "
    r"datetimes in UTC: datetime.datetime.now\(datetime.UTC\).",
    category=DeprecationWarning,
)

# Python3.12 generates deprecation warnings like:
# "This process (pid=6558) is multi-threaded, use of fork() may lead to deadlocks in the child."
# Tracked in https://github.com/buildbot/buildbot/issues/7276
warnings.filterwarnings(
    "ignore",
    r"This process \(pid=\d+\) is multi-threaded, use of fork\(\) may lead "
    r"to deadlocks in the child\.",
    category=DeprecationWarning,
)

# Warnings comes from attr 24.1.0 because of automat
warnings.filterwarnings(
    "ignore",
    r"The `hash` argument is deprecated in favor of `unsafe_hash` "
    r"and will be removed in or after August 2025\.",
    category=DeprecationWarning,
)

warnings.filterwarnings(
    "ignore",
    r"twisted.web.resource._UnsafeErrorPage.__init__ was deprecated in "
    r"Twisted 22.10.0; please use Use twisted.web.pages.errorPage instead, "
    r"which properly escapes HTML. instead",
    category=DeprecationWarning,
)

warnings.filterwarnings(
    "ignore",
    r"twisted.web.resource._UnsafeNoResource.__init__ was deprecated in "
    r"Twisted 22.10.0; please use Use twisted.web.pages.notFound instead, "
    r"which properly escapes HTML. instead",
    category=DeprecationWarning,
)

warnings.filterwarnings(
    "ignore",
    r"twisted.web.resource._UnsafeForbiddenResource.__init__ was deprecated in "
    r"Twisted 22.10.0; please use Use twisted.web.pages.forbidden instead, "
    r"which properly escapes HTML. instead",
    category=DeprecationWarning,
)
