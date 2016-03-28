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

from distutils.version import LooseVersion

# apply the same patches the buildmaster does when it starts
from buildbot import monkeypatches
monkeypatches.patch_all(for_tests=True)

# enable deprecation warnings
import warnings
warnings.filterwarnings('always', category=DeprecationWarning)

import sys
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
    # the warning has been there since forever, but would be catched by the next lastResort logger
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
# they will be imported and when warning should be catched.
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerModuleWarning

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

# All deprecated modules should be loaded, consider future
# DeprecatedWorkerModuleWarning in tests as errors.
# All DeprecatedWorkerNameWarning warnings should be explicitly catched too,
# so fail on any DeprecatedWorkerAPIWarning.
warnings.filterwarnings('error', category=DeprecatedWorkerAPIWarning)
