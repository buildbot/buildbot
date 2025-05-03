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

"""
A complete re-implementation of the database connector components, but without
using a database.  These classes should pass the same tests as are applied to
the real connector components.
"""

from .build_data import BuildData
from .builders import Builder
from .builders import BuilderMaster
from .builders import BuildersTags
from .buildrequests import BuildRequest
from .buildrequests import BuildRequestClaim
from .builds import Build
from .builds import BuildProperty
from .buildsets import Buildset
from .buildsets import BuildsetProperty
from .buildsets import BuildsetSourceStamp
from .changes import Change
from .changes import ChangeFile
from .changes import ChangeProperty
from .changes import ChangeUser
from .changesources import ChangeSource
from .changesources import ChangeSourceMaster
from .codebases import Codebase
from .codebases import CodebaseBranch
from .codebases import CodebaseCommit
from .connector import FakeDBConnector
from .logs import Log
from .logs import LogChunk
from .masters import Master
from .projects import Project
from .schedulers import Scheduler
from .schedulers import SchedulerChange
from .schedulers import SchedulerMaster
from .sourcestamps import Patch
from .sourcestamps import SourceStamp
from .state import Object
from .state import ObjectState
from .steps import Step
from .tags import Tag
from .test_result_sets import TestResultSet
from .test_results import TestCodePath
from .test_results import TestName
from .test_results import TestResult
from .users import User
from .users import UserInfo
from .workers import ConfiguredWorker
from .workers import ConnectedWorker
from .workers import Worker

__all__ = [
    'Build',
    'BuildData',
    'BuildProperty',
    'BuildRequest',
    'BuildRequestClaim',
    'Builder',
    'BuilderMaster',
    'BuildersTags',
    'Buildset',
    'BuildsetProperty',
    'BuildsetSourceStamp',
    'Change',
    'ChangeFile',
    'ChangeProperty',
    'ChangeSource',
    'ChangeSourceMaster',
    'ChangeUser',
    'Codebase',
    'CodebaseBranch',
    'CodebaseCommit',
    'ConfiguredWorker',
    'ConnectedWorker',
    'FakeDBConnector',
    'Log',
    'LogChunk',
    'Master',
    'Object',
    'ObjectState',
    'Patch',
    'Project',
    'Scheduler',
    'SchedulerChange',
    'SchedulerMaster',
    'SourceStamp',
    'Step',
    'Tag',
    'TestCodePath',
    'TestName',
    'TestResult',
    'TestResultSet',
    'User',
    'UserInfo',
    'Worker',
]
