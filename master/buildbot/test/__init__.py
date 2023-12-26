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
from unittest import mock

import setuptools  # force import setuptools before any other distutils imports
from sqlalchemy.exc import RemovedIn20Warning

from buildbot import monkeypatches
from buildbot.test.util.warnings import assertProducesWarning  # noqa pylint: disable=wrong-import-position
from buildbot.test.util.warnings import assertProducesWarnings  # noqa pylint: disable=wrong-import-position
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
warnings.filterwarnings('ignore', "Not importing directory.*docker': missing __init__.py",
                        category=ImportWarning)

# FIXME: needs to be sorted out (#3666)
warnings.filterwarnings('ignore', "1300 Invalid utf8 character string")

# twisted.compat.execfile is using 'U' https://twistedmatrix.com/trac/ticket/9023
warnings.filterwarnings('ignore', "'U' mode is deprecated", DeprecationWarning)

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

# Python 3.7 adds a deprecation importing ABCs from collection.
# Such imports are made in dependencies (e.g moto, werzeug, pyparsing)
warnings.filterwarnings('ignore', ".*Using or importing the ABCs from 'collections'.*",
                        DeprecationWarning)

# more 3.7 warning from moto
warnings.filterwarnings('ignore', r".*Use 'list\(elem\)' or iteration over elem instead.*",
                        DeprecationWarning)
warnings.filterwarnings('ignore', r".*distutils Version classes are deprecated.*",
                        DeprecationWarning)

# ignore ResourceWarnings for unclosed sockets for the pg8000 driver on Python 3+ (tech debt: #4508)
if sys.version_info[0] >= 3 and "pg8000" in os.getenv("BUILDBOT_TEST_DB_URL", ""):
    warnings.filterwarnings('ignore', ".*unclosed .*socket", ResourceWarning)

# ignore ResourceWarnings when connecting to a HashiCorp vault via hvac in integration tests
warnings.filterwarnings('ignore', r".*unclosed .*socket.*raddr=.*, 8200[^\d]", ResourceWarning)

# Python 3.5-3.8 shows this warning
warnings.filterwarnings('ignore', ".*the imp module is deprecated in favour of importlib*")

# Python 3.3-3.7 show this warning and in invoked from autobahn
warnings.filterwarnings('ignore', ".*time.clock has been deprecated in Python 3.3.*")

# ignore an attrs API warning for APIs used in dependencies
warnings.filterwarnings('ignore', ".*The usage of `cmp` is deprecated and will be removed "
                                  "on or after.*", DeprecationWarning)

# ignore warnings from importing lib2to3 via buildbot_pkg ->
# setuptools.command.build_py -> setuptools.lib2to3_ex -> lib2to3
# https://github.com/pypa/setuptools/issues/2086
warnings.filterwarnings('ignore', ".*lib2to3 package is deprecated",
                        category=PendingDeprecationWarning)

# on python 3.9, this warning is generated by the stdlib
warnings.filterwarnings('ignore', ".*The loop argument is deprecated since Python",
                        category=DeprecationWarning)

# This warning is generated by the EC2 latent
warnings.filterwarnings('ignore', ".*stream argument is deprecated. Use stream parameter",
                        category=DeprecationWarning)

# Botocore imports deprecated urllib3.contrib.pyopenssl for backwards compatibility that we don't
# use. See https://github.com/boto/botocore/issues/2744
warnings.filterwarnings('ignore', ".*'urllib3.contrib.pyopenssl' module is deprecated",
                        category=DeprecationWarning)

# pipes is still used in astroid and buildbot_worker in default installation
warnings.filterwarnings('ignore', "'pipes' is deprecated and slated for removal in Python 3.13",
                        category=DeprecationWarning)

# boto3 shows this warning when on old Python
warnings.filterwarnings('ignore', ".*Boto3 will no longer support Python .*",
                        category=Warning)

# autobahn is not updated for Twisted 22.04 and newer
warnings.filterwarnings("ignore", "twisted.web.resource.NoResource was deprecated in",
                        category=DeprecationWarning)

# Buildbot shows this warning after upgrading to Twisted 23.10
warnings.filterwarnings('ignore', ".*unclosed event loop.*", category=Warning)

# Ignore sqlalchemy 1.5 warning
# sqlalchemy.exc.RemovedIn20Warning: Deprecated API features detected! These feature(s) are not
# compatible with SQLAlchemy 2.0. To prevent incompatible upgrades prior to updating applications,
# ensure requirements files are pinned to "sqlalchemy<2.0". Set environment variable
# SQLALCHEMY_WARN_20=1 to show all deprecation warnings.  Set environment variable
# SQLALCHEMY_SILENCE_UBER_WARNING=1 to silence this message. (Background on SQLAlchemy 2.0
# at: https://sqlalche.me/e/b8d9) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
warnings.filterwarnings("ignore", category=RemovedIn20Warning)

# This warning is generated by twisted with Python 3.12.
# Should be fixed by https://github.com/twisted/twisted/pull/12027
warnings.filterwarnings('ignore', r"the \(type, exc, tb\) signature of throw\(\) is deprecated, "
                        "use the single-arg signature instead",
                        category=DeprecationWarning)

# This warning is generated by graphql-core with Python 3.12.
# See https://github.com/graphql-python/graphql-core/issues/211
warnings.filterwarnings('ignore', "'typing.ByteString' is deprecated and slated for removal in "
                        "Python 3.14", category=DeprecationWarning)

# When using Python 3.12, this generates some dependent package
warnings.filterwarnings('ignore', r"datetime.datetime.utcnow\(\) is deprecated and scheduled for "
                        r"removal in a future version. Use timezone-aware objects to represent "
                        r"datetimes in UTC: datetime.datetime.now\(datetime.UTC\).",
                        category=DeprecationWarning)

# Python3.12 generates deprecation warnings like:
# "This process (pid=6558) is multi-threaded, use of fork() may lead to deadlocks in the child."
# Tracked in https://github.com/buildbot/buildbot/issues/7276
warnings.filterwarnings("ignore",
                        r"This process \(pid=\d+\) is multi-threaded, use of fork\(\) may lead "
                        r"to deadlocks in the child\.",
                        category=DeprecationWarning)
