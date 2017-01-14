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

from buildbot.steps.worker import CompositeStepMixin
from buildbot.steps.worker import CopyDirectory
from buildbot.steps.worker import FileExists
from buildbot.steps.worker import MakeDirectory
from buildbot.steps.worker import RemoveDirectory
from buildbot.steps.worker import SetPropertiesFromEnv
from buildbot.steps.worker import WorkerBuildStep
# pylint: disable=unused-import
from buildbot.worker_transition import deprecatedWorkerModuleAttribute
from buildbot.worker_transition import reportDeprecatedWorkerModuleUsage

__all__ = [
    'CompositeStepMixin',
    'CopyDirectory',
    'FileExists',
    'MakeDirectory',
    'RemoveDirectory',
    'SetPropertiesFromEnv',
]

reportDeprecatedWorkerModuleUsage(
    "'{old}' module is deprecated, use "
    "'buildbot.steps.worker' module instead".format(old=__name__))


deprecatedWorkerModuleAttribute(locals(), WorkerBuildStep)
del WorkerBuildStep  # noqa
