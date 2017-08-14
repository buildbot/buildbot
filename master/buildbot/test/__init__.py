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

import sys
import warnings

from distutils.version import LooseVersion

from buildbot import monkeypatches

# apply the same patches the buildmaster does when it starts
monkeypatches.patch_all(for_tests=True)

# enable deprecation warnings
warnings.filterwarnings('always', category=DeprecationWarning)

if sys.version_info[:2] < (3, 2):
    # Setup logging unhandled messages to stderr.
    # Since Python 3.2 similar functionality implemented through
    # logging.lastResort handler.
    # Significant difference between this approach and Python 3.2 last resort
    # approach is that in the current approach only records with log level
    # equal or above to the root logger log level will be printed (WARNING by
    # default). For example, there still will be warnings about missing
    # handler for log if INFO or DEBUG records will be logged (but at least
    # WARNINGs and ERRORs will be printed).
    import logging
    _handler = logging.StreamHandler()

    # Ignore following Exception logs:
    #       Traceback (most recent call last):
    #       File "[..]site-packages/sqlalchemy/pool.py", line 290, in _close_connection
    #       self._dialect.do_close(connection)
    #       File "[..]/sqlalchemy/engine/default.py", line 426, in do_close
    #       dbapi_connection.close()
    #       ProgrammingError: SQLite objects created in a thread can only be used in that same thread.
    #       The object was created in thread id 123145306509312 and this is thread id 140735272824832
    # sqlalchemy is closing pool connections from the main thread, which sqlite does not like
    # the warning has been there since forever, but would be caught by the next lastResort logger
    logging.getLogger("sqlalchemy.pool.SingletonThreadPool").addHandler(None)
    logging.getLogger().addHandler(_handler)
# import mock so we bail out early if it's not installed
try:
    import mock
    mock = mock
except ImportError:
    raise ImportError("\nBuildbot tests require the 'mock' module; "
                      "try 'pip install mock'")

if LooseVersion(mock.__version__) < LooseVersion("0.8"):
    raise ImportError("\nBuildbot tests require mock version 0.8.0 or "
                      "higher; try 'pip install -U mock'")

# Force loading of deprecated modules and check that appropriate warnings
# were emitted.
# Without explicit load of deprecated modules it's hard to predict when
# they will be imported and when warning should be caught.
from buildbot.test.util.warnings import assertProducesWarning  # noqa pylint: disable=wrong-import-position
from buildbot.worker_transition import DeprecatedWorkerAPIWarning  # noqa pylint: disable=wrong-import-position
from buildbot.worker_transition import DeprecatedWorkerModuleWarning  # noqa pylint: disable=wrong-import-position

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.buildslave' module is deprecated"):
    import buildbot.buildslave as _  # noqa

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.steps\.slave' module is deprecated"):
    import buildbot.steps.slave as _  # noqa

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.process\.slavebuilder' module is deprecated"):
    import buildbot.process.slavebuilder as _  # noqa

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.db\.buildslaves' module is deprecated"):
    import buildbot.db.buildslaves as _  # noqa

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.buildslave\.ec2' module is deprecated"):
    import buildbot.buildslave.ec2 as _  # noqa

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.buildslave\.libvirt' module is deprecated"):
    import buildbot.buildslave.libvirt as _  # noqa

with assertProducesWarning(
        DeprecatedWorkerModuleWarning,
        message_pattern=r"'buildbot\.buildslave\.openstack' module is deprecated"):
    import buildbot.buildslave.openstack as _  # noqa

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
