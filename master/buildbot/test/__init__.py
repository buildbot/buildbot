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

import os
import sys
import warnings
from pkg_resources import parse_version

import setuptools  # force import setuptools before any other distutils imports

from buildbot import monkeypatches
from buildbot.test.util.warnings import assertProducesWarning  # noqa pylint: disable=wrong-import-position
from buildbot.test.util.warnings import assertProducesWarnings  # noqa pylint: disable=wrong-import-position
from buildbot.warnings import DeprecatedApiWarning  # noqa pylint: disable=wrong-import-position

# import mock so we bail out early if it's not installed
try:
    import mock
    [mock]
except ImportError as e:
    raise ImportError("\nBuildbot tests require the 'mock' module; "
                      "try 'pip install mock'") from e

# apply the same patches the buildmaster does when it starts
monkeypatches.patch_all(for_tests=True)

# enable deprecation warnings
warnings.filterwarnings('always', category=DeprecationWarning)

if parse_version(mock.__version__) < parse_version("0.8"):
    raise ImportError("\nBuildbot tests require mock version 0.8.0 or "
                      "higher; try 'pip install -U mock'")

[setuptools]  # force use for pylint

# This is where we load deprecated module-level APIs to ignore warning produced by importing them.
# After the deprecated API has been removed, leave at least one instance of the import in a
# commented state as reference.


with assertProducesWarnings(DeprecatedApiWarning,
                            messages_patterns=[
                                r" buildbot\.status\.base has been deprecated",
                                r" buildbot\.status\.build has been deprecated",
                                r" buildbot\.status\.buildrequest has been deprecated",
                                r" buildbot\.status\.event has been deprecated",
                                r" buildbot\.status\.buildset has been deprecated",
                                r" buildbot\.status\.master has been deprecated",
                                r" buildbot\.status\.worker has been deprecated",
                            ]):
    import buildbot.status.base as _  # noqa
    import buildbot.status.build as _  # noqa
    import buildbot.status.buildrequest as _  # noqa
    import buildbot.status.event as _  # noqa
    import buildbot.status.buildset as _  # noqa
    import buildbot.status.master as _  # noqa
    import buildbot.status.worker as _  # noqa

# All deprecated modules should be loaded, consider future warnings in tests as errors.
# In order to not pollute the test outputs,
# warnings in tests shall be forcefully tested with assertProducesWarning,
# or shutdown using the warning module
warnings.filterwarnings('error')
# if buildbot_worker is installed in pip install -e mode, then the docker directory will
# match "import docker", and produce a warning.
# We just suppress this warning instead of doing silly workaround.
warnings.filterwarnings('ignore', "Not importing directory.*docker': missing __init__.py",
                        category=ImportWarning)

# FIXME: needs to be sorted out (#3666)
warnings.filterwarnings('ignore', "1300 Invalid utf8 character string")

# twisted.compat.execfile is using 'U' https://twistedmatrix.com/trac/ticket/9023
warnings.filterwarnings('ignore', "'U' mode is deprecated", DeprecationWarning)

# sqlalchemy.migrate is calling inspect.getargspec()
# https://bugs.launchpad.net/sqlalchemy-migrate/+bug/1662472
warnings.filterwarnings('ignore', r"inspect.getargspec\(\) is deprecated")

# twisted.python.filepath and trial are using bytes file paths when
# the "native" file path (Unicode) should be used on Windows.
warnings.filterwarnings('ignore',
                        "The Windows bytes API has been "
                        "deprecated, use Unicode filenames instead")
# moto warning v1.0.0
warnings.filterwarnings('ignore', "Flags not at the start of the expression")
warnings.filterwarnings('ignore', r"object\(\) takes no parameters")

# this warning happens sometimes on python3.4
warnings.filterwarnings('ignore', r"The value of convert_charrefs will become True in 3.5")

# Twisted 18.4+ adds a deprecation warning and still use the deprecated API in its own code!
warnings.filterwarnings('ignore', ".*getClientIP was deprecated.*", DeprecationWarning)

# Python 3.7 adds a deprecation warning formatargspec.
# The signature api that replaces it is not available in 2.7
warnings.filterwarnings('ignore', ".*`formatargspec` is deprecated.*", DeprecationWarning)

# Python 3.7 adds a deprecation importing ABCs from collection.
# Such imports are made in dependencies (e.g moto, werzeug, pyparsing)
warnings.filterwarnings('ignore', ".*Using or importing the ABCs from 'collections'.*",
                        DeprecationWarning)

# more 3.7 warning from moto
warnings.filterwarnings('ignore', r".*Use 'list\(elem\)' or iteration over elem instead.*",
                        DeprecationWarning)

# ignore ResourceWarnings for unclosed sockets for the pg8000 driver on Python 3+ (tech debt: #4508)
if sys.version_info[0] >= 3 and "pg8000" in os.getenv("BUILDBOT_TEST_DB_URL", ""):
    warnings.filterwarnings('ignore', ".*unclosed .*socket", ResourceWarning)

# Python 3.5 on CircleCI shows this warning
warnings.filterwarnings('ignore', ".*the imp module is deprecated in favour of importlib*")

# sqlalchemy-migrate uses deprecated api from sqlalchemy https://review.openstack.org/#/c/648072/
warnings.filterwarnings('ignore', ".*Engine.contextual_connect.*", DeprecationWarning)

# ignore an attrs API warning for APIs used in dependencies
warnings.filterwarnings('ignore', ".*The usage of `cmp` is deprecated and will be removed "
                                  "on or after.*", DeprecationWarning)

# ignore a warning emitted by pkg_resources when importing certain namespace packages
warnings.filterwarnings('ignore', ".*Not importing directory .*/zope: missing __init__",
                        category=ImportWarning)
warnings.filterwarnings('ignore', ".*Not importing directory .*/sphinxcontrib: missing __init__",
                        category=ImportWarning)

# ignore warnings from importing lib2to3 via buildbot_pkg ->
# setuptools.command.build_py -> setuptools.lib2to3_ex -> lib2to3
# https://github.com/pypa/setuptools/issues/2086
warnings.filterwarnings('ignore', ".*lib2to3 package is deprecated",
                        category=PendingDeprecationWarning)
