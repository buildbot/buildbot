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

# This module is left for backward compatibility of old-named worker API.
# It should never be imported by Buildbot.

from __future__ import absolute_import
from __future__ import print_function

from buildbot.process.workerforbuilder import AbstractWorkerForBuilder as _AbstractWorkerForBuilder
from buildbot.process.workerforbuilder import LatentWorkerForBuilder as _LatentWorkerForBuilder
from buildbot.process.workerforbuilder import WorkerForBuilder as _WorkerForBuilder
from buildbot.worker_transition import deprecatedWorkerModuleAttribute
from buildbot.worker_transition import reportDeprecatedWorkerModuleUsage

reportDeprecatedWorkerModuleUsage(
    "'{old}' module is deprecated, use "
    "'buildbot.process.workerforbuilder' module instead".format(old=__name__))


deprecatedWorkerModuleAttribute(locals(), _AbstractWorkerForBuilder,
                                compat_name="AbstractSlaveBuilder",
                                new_name="AbstractWorkerForBuilder")
deprecatedWorkerModuleAttribute(locals(), _WorkerForBuilder,
                                compat_name="SlaveBuilder",
                                new_name="WorkerForBuilder")
deprecatedWorkerModuleAttribute(locals(), _LatentWorkerForBuilder,
                                compat_name="LatentSlaveBuilder",
                                new_name="LatentWorkerForBuilder")
